import pandas as pd
import numpy as np
import os
import json
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from app.config import Config

class ShadowStrategy(ABC):
    """
    Abstract Base Class for a Trading Genotype.
    Runs in 'Shadow Mode' (Paper Trading) to track performance.
    """
    def __init__(self, name: str, direction: str = 'BOTH', params: dict = None):
        self.name = name
        self.direction = direction # 'BOTH', 'LONG', 'SHORT'
        self.params = params if params else {}
        
        self.phantom_equity = 10000.0 # Virtual $10k start
        self.peak_equity = 10000.0
        self.max_drawdown = 0.0 # Percent (0.0 to 1.0)
        
        self.active_trade = None # Dict: {'entry': float, 'type': 'BUY'/'SELL'}
        self.trade_history = [] # List of closed trades
        self.win_streak = 0
        self.loss_streak = 0
        
    @abstractmethod
    def _generate_raw_signal(self, df: pd.DataFrame, indicators: dict, mtf_data: dict) -> dict:
        """Internal method to generate signal BEFORE directional filtering."""
        pass
        
    def generate_signal(self, df: pd.DataFrame, indicators: dict, mtf_data: dict) -> dict:
        """Public method: Generates signal and then FILTERS it based on direction."""
        signal = self._generate_raw_signal(df, indicators, mtf_data)
        
        # Directional Filtering (The Hydra Logic)
        if signal['action'] == 'BUY' and self.direction == 'SHORT':
            return {'action': 'HOLD', 'confidence': 0, 'sl': 0, 'tp': 0}
            
        if signal['action'] == 'SELL' and self.direction == 'LONG':
            return {'action': 'HOLD', 'confidence': 0, 'sl': 0, 'tp': 0}
            
        return signal
        
    def update_performance(self, current_price: float):
        """Updates Phantom Equity based on active virtual trades and tracks Drawdown."""
        equity_now = self.phantom_equity
        
        # 1. Calculate Floating PnL if active trade
        if self.active_trade:
            entry = self.active_trade['entry']
            direction = self.active_trade['type']
            vol_scale = 1000 # Scaling
            
            if direction == 'BUY':
                floating = (current_price - entry) * vol_scale
            else:
                floating = (entry - current_price) * vol_scale
            
            equity_now += floating
            
            # Check Stop/Take Profit (Simulation)
            sl = self.active_trade['sl']
            tp = self.active_trade['tp']
            
            closed_pnl = 0.0
            is_closed = False
            
            if direction == 'BUY':
                if current_price <= sl: closed_pnl = (sl - entry); is_closed = True
                elif current_price >= tp: closed_pnl = (tp - entry); is_closed = True
            elif direction == 'SELL':
                if current_price >= sl: closed_pnl = (entry - sl); is_closed = True
                elif current_price <= tp: closed_pnl = (entry - tp); is_closed = True
            
            if is_closed:
                realized = closed_pnl * vol_scale
                self.phantom_equity += realized
                equity_now = self.phantom_equity # Update base
                
                self.trade_history.append({'pnl': realized, 'time': datetime.now()})
                if realized > 0:
                    self.win_streak += 1
                    self.loss_streak = 0
                else:
                    self.loss_streak += 1
                    self.win_streak = 0
                self.active_trade = None

        # 2. Track Drawdown
        if equity_now > self.peak_equity:
            self.peak_equity = equity_now
        
        dd = (self.peak_equity - equity_now) / self.peak_equity
        if dd > self.max_drawdown:
            self.max_drawdown = dd
            
    def get_quality_score(self, mtf_regime: dict = None) -> float:
        """
        Calculates a 'Smart Score' for leader selection.
        Score = (Equity * RegimeBoost) / (1 + DrawdownPenalty)
        """
        base_score = self.phantom_equity
        
        # 1. Regime Boost (Predictive Switching)
        boost = 1.0
        if mtf_regime:
            hurst = mtf_regime.get('M15', {}).get('hurst', 0.5)
            
            # Boost logic needs to check Class Name string AND Direction
            regime_trend = mtf_regime.get('trend', 'NEUTRAL') # Expecting 'BULLISH', 'BEARISH', 'RANGING'
            
            # TrendHawk Logic (Trend Following)
            if "TrendHawk" in self.name:
                if hurst > 0.55: # Trending Regime
                    # Directional Matching
                    if regime_trend == 'BULLISH':
                        if self.direction == 'LONG': boost = 1.3 # Strong Boost
                        elif self.direction == 'SHORT': boost = 0.7 # Strong Penalty
                    elif regime_trend == 'BEARISH':
                        if self.direction == 'SHORT': boost = 1.3
                        elif self.direction == 'LONG': boost = 0.7
                else: 
                     # Not trending? Penalize TrendHawk slightly
                     boost = 0.9
                     
            # MeanReverter Logic (Counter Trend)
            elif "MeanRev" in self.name:
                if hurst < 0.45: # Mean Reversion Regime
                     boost = 1.2
                     # In Range, direction matters less, but we can prefer fading the macro trend?
                     # For now, generic boost is fine.
                else:
                     boost = 0.8 # Don't mean revert in trends
                
        # 2. Drawdown Penalty (Stability)
        # 10% DD = 1.2 penalty divisor, 20% DD = 1.4
        penalty = 1 + (self.max_drawdown * 2.0) 
        
        final_score = (base_score * boost) / penalty
        return final_score

class TrendHawk(ShadowStrategy):
    """
    1. The 'Incumbent': Fractal Breakouts + Trend Following.
    Params: 'period' (Lookback for High/Low)
    """
    def _generate_raw_signal(self, df: pd.DataFrame, indicators: dict, mtf_data: dict) -> dict:
        current_price = df.iloc[-1]['close']
        
        # Dynamic Period
        period = self.params.get('period', 20)
        
        # FIX 1: Robust Indicator Lookup (Handle Case Sensitivity)
        # Sensor sends 'ema_50', we want that.
        ema_50 = indicators.get('ema_50', indicators.get('EMA_50', 0))
        
        # FIX 2: Correct Breakout Logic (Price > Previous N Highs)
        # We must shift(1) to exclude the current forming candle from the reference
        prev_highs = df['high'].shift(1).rolling(period).max()
        prev_lows = df['low'].shift(1).rolling(period).min()
        
        high_x = prev_highs.iloc[-1]
        low_x = prev_lows.iloc[-1]
        
        # Trend Filter
        if current_price > ema_50:
            # Bullish Breakout
            if current_price >= high_x:
                p_sl = low_x 
                risk = current_price - p_sl
                if risk <= 0: return {'action': 'HOLD', 'confidence': 0, 'sl': 0, 'tp': 0}
                return {'action': 'BUY', 'confidence': 0.85, 'sl': p_sl, 'tp': current_price + 2*risk}
            else:
                 return {'action': 'HOLD', 'confidence': 0.0, 'sl': 0, 'tp': 0, 'reason': f"Price {current_price:.5f} < Breakout {high_x:.5f}"}
                
        elif current_price < ema_50:
            # Bearish Breakout
            if current_price <= low_x:
                p_sl = high_x 
                risk = p_sl - current_price
                if risk <= 0: return {'action': 'HOLD', 'confidence': 0, 'sl': 0, 'tp': 0}
                return {'action': 'SELL', 'confidence': 0.85, 'sl': p_sl, 'tp': current_price - 2*risk}
            else:
                 return {'action': 'HOLD', 'confidence': 0.0, 'sl': 0, 'tp': 0, 'reason': f"Price {current_price:.5f} > Breakout {low_x:.5f}"}
                
        return {'action': 'HOLD', 'confidence': 0.0, 'sl': 0, 'tp': 0, 'reason': "Against Trend (EMA50)"}

class MeanReverter(ShadowStrategy):
    """
    2. The 'Contrarian': Fading Bollinger Band Extremes.
    Params: 'std_dev' (Band Width)
    """
    def _generate_raw_signal(self, df: pd.DataFrame, indicators: dict, mtf_data: dict) -> dict:
        latest = df.iloc[-1]
        close = latest['close']
        
        # FIX 1: Robust Keys
        bb_upper_std = indicators.get('bb_upper', indicators.get('BB_Upper', 0))
        bb_lower_std = indicators.get('bb_lower', indicators.get('BB_Lower', 0))
        
        if bb_upper_std == 0: 
             return {'action': 'HOLD', 'confidence': 0, 'sl': 0, 'tp': 0, 'reason': "Bollinger Data Missing"}
        
        basis = (bb_upper_std + bb_lower_std) / 2
        std_width = bb_upper_std - basis
        
        user_std = self.params.get('std_dev', 2.0)
        width_scalar = user_std / 2.0
        
        my_upper = basis + (std_width * width_scalar)
        my_lower = basis - (std_width * width_scalar)
        
        rsi = indicators.get('rsi', indicators.get('RSI_14', 50))
        ema_50 = indicators.get('ema_50', indicators.get('EMA_50', close))
        
        # Fade Highs (Sell at Top of Range)
        if close > my_upper and rsi > 70:
            return {'action': 'SELL', 'confidence': 0.75, 'sl': close * 1.002, 'tp': ema_50}
            
        # Fade Lows (Buy at Bottom of Range)
        if close < my_lower and rsi < 30:
            return {'action': 'BUY', 'confidence': 0.75, 'sl': close * 0.998, 'tp': ema_50}
            
        return {'action': 'HOLD', 'confidence': 0.0, 'sl': 0, 'tp': 0, 'reason': "Inside Bands"}

class Sniper(ShadowStrategy):
    """
    3. The 'Perfectionist': Only trades if multiple Timeframes align.
    """
    def _generate_raw_signal(self, df: pd.DataFrame, indicators: dict, mtf_data: dict) -> dict:
         if 'H1' not in mtf_data or mtf_data['H1'].empty:
             return {'action': 'HOLD', 'confidence': 0, 'sl': 0, 'tp': 0}
             
         h1_df = mtf_data['H1']
         h1_close = h1_df.iloc[-1]['close']
         h1_ma = h1_df['close'].rolling(50).mean().iloc[-1] # Simple H1 Trend
         
         current_price = df.iloc[-1]['close']
         # FIX: Shift(1) here too
         high_20 = df['high'].shift(1).rolling(20).max().iloc[-1]
         low_20 = df['low'].shift(1).rolling(20).min().iloc[-1]
         ema_50 = indicators.get('ema_50', indicators.get('EMA_50', 0))
         
         # ... (Rest of logic similar to TrendHawk but checking H1)
         action = "HOLD"
         sl = 0
         tp = 0
         
         if current_price > ema_50 and current_price >= high_20:
             action = "BUY"
             sl = low_20
             tp = current_price + 2*(current_price - sl)
         elif current_price < ema_50 and current_price <= low_20:
             action = "SELL"
             sl = high_20
             tp = current_price - 2*(sl - current_price)
             
         if action == 'BUY':
             if h1_close > h1_ma:
                 return {'action': 'BUY', 'confidence': 0.95, 'sl': sl, 'tp': tp}
         elif action == 'SELL':
             if h1_close < h1_ma:
                 return {'action': 'SELL', 'confidence': 0.95, 'sl': sl, 'tp': tp}
                 
         return {'action': 'HOLD', 'confidence': 0.0, 'sl': 0, 'tp': 0, 'reason': "H1 Alignment Fail"}

class DarwinEngine:
    def __init__(self):
        self.strategies = []
        self.state_file = os.path.join(Config.BASE_DIR, "darwin_state.json")
        
        # === PROJECT HYDRA: GENERATE SWARM ===
        
        # 1. TrendHawk Variants (Fast/Med/Slow x Long/Short)
        periods = [10, 20, 50]
        directions = ['LONG', 'SHORT']
        
        for p in periods:
            for d in directions:
                name = f"TrendHawk_{d}_{p}p"
                self.strategies.append(
                    TrendHawk(name, direction=d, params={'period': p})
                )
                
        # 2. MeanReverter Variants (Tight/Std/Wide x Long/Short)
        devs = [1.5, 2.0, 2.5]
        for v in devs:
            for d in directions:
                lbl = "Tight" if v < 2.0 else "Wide" if v > 2.0 else "Std"
                name = f"MeanRev_{d}_{lbl}"
                self.strategies.append(
                    MeanReverter(name, direction=d, params={'std_dev': v})
                )
        
        # 3. Sniper (The Lone Wolf - Always Bundled for now)
        self.strategies.append(Sniper("Sniper_Elite", direction='BOTH'))
        
        # LOAD BRAIN MEMORY
        self.load_state()
        
        self.leader = self.strategies[0]
        self.last_scores = {}
        
    def load_state(self):
        """Restores evolution history from disk with MEMORY DECAY."""
        if not os.path.exists(self.state_file):
            return
            
        try:
            with open(self.state_file, 'r') as f:
                data = json.load(f)
                
            last_save_time = data.get('timestamp', None)
            decay_factor = 1.0
            
            # AGE CHECK: If memory is old (> 4 hours), compress the equity spread.
            # This prevents yesterday's winner from dominating today's different market.
            if last_save_time:
                try:
                    save_dt = datetime.fromisoformat(last_save_time)
                    hours_old = (datetime.now() - save_dt).total_seconds() / 3600
                    if hours_old > 4:
                        print(f"🧠 Memory is Stale ({hours_old:.1f}h). Applying MEMORY DECAY (50%).")
                        decay_factor = 0.5
                except:
                    pass

            for strat in self.strategies:
                if strat.name in data:
                    s_data = data[strat.name]
                    
                    # Restore Stats
                    raw_equity = s_data.get('equity', 10000.0)
                    
                    # Apply Decay to PnL (Normalize towards 10k)
                    pnl = raw_equity - 10000.0
                    strat.phantom_equity = 10000.0 + (pnl * decay_factor)
                    
                    strat.peak_equity = max(10000.0, strat.phantom_equity) # Reset peak to current decoded equity
                    strat.max_drawdown = s_data.get('dd', 0.0) * decay_factor # Reduce historical DD weight too
                    
                    # Reset Streaks on Session Change to allow fresh start
                    if decay_factor < 1.0:
                        strat.win_streak = 0
                        strat.loss_streak = 0
                    else:
                        strat.win_streak = s_data.get('wins', 0)
                        strat.loss_streak = s_data.get('losses', 0)
                        
            print(f"🧬 Darwin Memory Loaded. Ecosystem restored (Decay: {decay_factor}).")
        except Exception as e:
            print(f"Darwin Memory Load Error: {e}")

    def save_state(self):
        """Persists evolution history to disk."""
        data = {
            'timestamp': datetime.now().isoformat()
        }
        for strat in self.strategies:
            data[strat.name] = {
                'equity': strat.phantom_equity,
                'peak': strat.peak_equity,
                'dd': strat.max_drawdown,
                'wins': strat.win_streak,
                'losses': strat.loss_streak
            }
        
        try:
            # Atomic write
            temp = self.state_file + ".tmp"
            with open(temp, 'w') as f:
                json.dump(data, f, indent=4)
            os.replace(temp, self.state_file)
        except Exception as e:
            print(f"Darwin Save Error: {e}")

    def update(self, df: pd.DataFrame, indicators: dict, mtf_data: dict):
        current_price = df.iloc[-1]['close']
        regime_context = mtf_data.get('analysis', {}) 
        
        for strat in self.strategies:
            strat.update_performance(current_price)
            if not strat.active_trade:
                signal = strat.generate_signal(df, indicators, mtf_data)
                if signal['action'] != 'HOLD':
                    strat.active_trade = {
                        'entry': current_price,
                        'type': signal['action'],
                        'sl': signal['sl'],
                        'tp': signal['tp']
                    }
                    
        # 3. Determine Leader (SMART SCORING)
        self.strategies.sort(key=lambda s: s.get_quality_score(regime_context), reverse=True)
        self.leader = self.strategies[0]
        self.last_scores = {s.name: s.get_quality_score(regime_context) for s in self.strategies}
        
        # 4. Save Memory
        self.save_state()
        
    def get_alpha_signal(self, df, indicators, mtf_data) -> dict:
        best_strat_name = self.leader.name
        signal = self.leader.generate_signal(df, indicators, mtf_data)
        signal['source'] = f"DarwinLeader::{best_strat_name}"
        signal['darwin_score'] = self.last_scores.get(best_strat_name, 0)
        return signal

    def get_leaderboard(self) -> str:
        # Hydra Upgrade: Only show Top 5 to avoid console spam
        s = "Darwin Smart Leaderboard (Top 5):\n"
        for i, strat in enumerate(self.strategies[:5]):
            score = self.last_scores.get(strat.name, 0)
            s += f" {i+1}. {strat.name}: Score {score:.0f} (Eq: ${strat.phantom_equity:.0f})\n"
        return s

    def get_swarm_state(self) -> list:
        """Returns full state of all strategies for Dashboard."""
        data = []
        for s in self.strategies:
            data.append({
                "name": s.name,
                "equity": s.phantom_equity,
                "score": self.last_scores.get(s.name, 0),
                "wins": s.win_streak,
                "losses": s.loss_streak,
                "drawdown": s.max_drawdown,
                "peak": s.peak_equity,
                "direction": s.direction
            })
        # Sort by Score implicitly via the engine's sort order (which happens in update)
        return data
