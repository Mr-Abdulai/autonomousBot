import pandas as pd
import numpy as np
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
            
            # Boost logic needs to check Class Name string
            if "TrendHawk" in self.name and hurst > 0.55:
                boost = 1.2 # trend regime favors TrendHawk
            elif "MeanRev" in self.name and hurst < 0.45:
                boost = 1.2 # chop regime favors MeanReverter
                
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
        
        # Rolling High/Low based on dynamic period
        high_x = df['high'].rolling(period).max().iloc[-1]
        low_x = df['low'].rolling(period).min().iloc[-1]
        ema_50 = indicators.get('EMA_50', 0)
        
        # Trend Filter
        if current_price > ema_50:
            # Bullish Breakout
            if current_price >= high_x:
                p_sl = low_x 
                risk = current_price - p_sl
                if risk <= 0: return {'action': 'HOLD', 'confidence': 0, 'sl': 0, 'tp': 0}
                return {'action': 'BUY', 'confidence': 0.85, 'sl': p_sl, 'tp': current_price + 2*risk}
                
        elif current_price < ema_50:
            # Bearish Breakout
            if current_price <= low_x:
                p_sl = high_x 
                risk = p_sl - current_price
                if risk <= 0: return {'action': 'HOLD', 'confidence': 0, 'sl': 0, 'tp': 0}
                return {'action': 'SELL', 'confidence': 0.85, 'sl': p_sl, 'tp': current_price - 2*risk}
                
        return {'action': 'HOLD', 'confidence': 0.0, 'sl': 0, 'tp': 0}

class MeanReverter(ShadowStrategy):
    """
    2. The 'Contrarian': Fading Bollinger Band Extremes.
    Params: 'std_dev' (Band Width)
    """
    def _generate_raw_signal(self, df: pd.DataFrame, indicators: dict, mtf_data: dict) -> dict:
        latest = df.iloc[-1]
        close = latest['close']
        
        # We need to manually calc dynamic bands if they aren't pre-calced
        # But for efficiency, we can use the pre-calced BB_Upper (2.0) and scale the width?
        # Or just re-calc. Shadow mode speed is critical.
        # Let's approximate: Width = (Upper - Basis). New Width = Width * (Desired / 2.0).
        
        bb_upper_std = indicators.get('BB_Upper', 0)
        bb_lower_std = indicators.get('BB_Lower', 0)
        
        if bb_upper_std == 0: return {'action': 'HOLD', 'confidence': 0, 'sl': 0, 'tp': 0}
        
        basis = (bb_upper_std + bb_lower_std) / 2
        std_width = bb_upper_std - basis
        
        user_std = self.params.get('std_dev', 2.0)
        # Scale the width
        # If user wants 2.5, and standard is 2.0.
        # New Width = Old Width * (2.5 / 2.0)
        width_scalar = user_std / 2.0
        
        my_upper = basis + (std_width * width_scalar)
        my_lower = basis - (std_width * width_scalar)
        
        rsi = indicators.get('RSI_14', 50)
        ema_50 = indicators.get('EMA_50', close)
        
        # Fade Highs (Sell at Top of Range)
        if close > my_upper and rsi > 70:
            return {'action': 'SELL', 'confidence': 0.75, 'sl': close * 1.002, 'tp': ema_50}
            
        # Fade Lows (Buy at Bottom of Range)
        if close < my_lower and rsi < 30:
            return {'action': 'BUY', 'confidence': 0.75, 'sl': close * 0.998, 'tp': ema_50}
            
        return {'action': 'HOLD', 'confidence': 0.0, 'sl': 0, 'tp': 0}

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
         
         # Reuse TrendHawk 20 logic without params
         # We need to instantiate a temp TrendHawk or call logic.
         # Cleaner: Just rewrite the logic to be safe.
         
         current_price = df.iloc[-1]['close']
         high_20 = df['high'].rolling(20).max().iloc[-1]
         low_20 = df['low'].rolling(20).min().iloc[-1]
         ema_50 = indicators.get('EMA_50', 0)
         
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
                 
         return {'action': 'HOLD', 'confidence': 0.0, 'sl': 0, 'tp': 0}

class DarwinEngine:
    def __init__(self):
        self.strategies = []
        
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
        
        self.leader = self.strategies[0]
        self.last_scores = {}
        
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
