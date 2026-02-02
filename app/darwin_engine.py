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
            
            # GOLD OPTIMIZED: Favor trend strategies more aggressively
            # A. TREND STRATEGIES (TrendHawk, MACD_Cross, Sniper)
            is_trend_strat = any(x in self.name for x in ["TrendHawk", "MACD_Cross", "Sniper"])
            if is_trend_strat:
                if hurst > 0.55: # Trending Regime - GOLD LOVES THIS
                    # Directional Matching with HIGHER boost for Gold
                    if regime_trend == 'BULLISH':
                        if self.direction == 'LONG' or self.direction == 'BOTH': boost = 1.5  # Gold: 1.5x vs 1.3x forex
                        elif self.direction == 'SHORT': boost = 0.6  # Penalize counter-trend harder
                    elif regime_trend == 'BEARISH':
                        if self.direction == 'SHORT' or self.direction == 'BOTH': boost = 1.5  # Gold: 1.5x
                        elif self.direction == 'LONG': boost = 0.6
                else: 
                     # Not trending? Slight penalty (Gold ranges less often)
                     boost = 0.85  # vs 0.9 for forex

            # B. MEAN REVERSION STRATEGIES (MeanReverter, RSI_Matrix)
            elif any(x in self.name for x in ["MeanRev", "RSI_Matrix"]):
                if hurst < 0.45: # Mean Reversion Regime
                     boost = 1.2
                else:
                     boost = 0.7 # Gold: Penalize MR harder in trends (vs 0.8x forex)
                
        # 2. Drawdown Penalty (Stability)
        # 10% DD = 1.2 penalty divisor, 20% DD = 1.4
        penalty = 1 + (self.max_drawdown * 2.0) 
        
        final_score = (base_score * boost) / penalty
        return final_score

class TrendHawk(ShadowStrategy):
    """
    1. The 'Incumbent': Fractal Breakouts + Trend Following.
    Params: 'period', 'require_trend' (bool)
    """
    def _generate_raw_signal(self, df: pd.DataFrame, indicators: dict, mtf_data: dict) -> dict:
        current_price = df.iloc[-1]['close']
        
        # Dynamic Period & Settings
        period = self.params.get('period', 20)
        require_trend = self.params.get('require_trend', False) # OPTIMIZED: Default False to catch reversals
        
        # FIX 1: Robust Indicator Lookup (Handle Case Sensitivity)
        # Sensor sends 'ema_50', we want that.
        ema_50 = indicators.get('ema_50', indicators.get('EMA_50', 0))
        
        # FIX 2: Correct Breakout Logic (Price > Previous N Highs)
        # We must shift(1) to exclude the current forming candle from the reference
        prev_highs = df['high'].shift(1).rolling(period).max()
        prev_lows = df['low'].shift(1).rolling(period).min()
        
        high_x = prev_highs.iloc[-1]
        low_x = prev_lows.iloc[-1]
        
        # Check for Insufficient Data (NaN)
        if pd.isna(high_x) or pd.isna(low_x):
             return {'action': 'HOLD', 'confidence': 0, 'sl': 0, 'tp': 0, 'reason': "Insufficient Data for Period"}
        
        # Trend Filter (Optional)
        is_bullish_trend = True
        is_bearish_trend = True
        
        if require_trend:
             is_bullish_trend = current_price > ema_50
             is_bearish_trend = current_price < ema_50
        
        if is_bullish_trend:
            # Bullish Breakout
            if current_price >= high_x:
                p_sl = low_x 
                risk = current_price - p_sl
                if risk <= 0: return {'action': 'HOLD', 'confidence': 0, 'sl': 0, 'tp': 0}
                return {'action': 'BUY', 'confidence': 0.85, 'sl': p_sl, 'tp': current_price + 2*risk}
            else:
                 return {'action': 'HOLD', 'confidence': 0.0, 'sl': 0, 'tp': 0, 'reason': f"Price {current_price:.5f} < Breakout {high_x:.5f}"}
                
        elif is_bearish_trend:
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
            # OPTIMIZED: Target Basis (SMA20) not EMA50 (too far)
            return {'action': 'SELL', 'confidence': 0.75, 'sl': close * 1.002, 'tp': basis}
            
        # Fade Lows (Buy at Bottom of Range)
        if close < my_lower and rsi < 30:
            # OPTIMIZED: Target Basis
            return {'action': 'BUY', 'confidence': 0.75, 'sl': close * 0.998, 'tp': basis}
            
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

class RSI_Matrix(ShadowStrategy):
    """
    RSI Mean Reversion Strategy (The Scalper).
    Logic:
        LONG: RSI < LowerBound (Oversold).
        SHORT: RSI > UpperBound (Overbought).
    """
    def __init__(self, lower=30, upper=70, direction="BOTH"):
        name = f"RSI_Matrix_{direction}_{lower}_{upper}"
        super().__init__(name, direction)
        self.lower = lower
        self.upper = upper

    def _generate_raw_signal(self, df, indicators, mtf_data):
        # FIX: Robust Key Lookup (Sensor uses 'rsi', legacy uses 'RSI_14')
        rsi = indicators.get('rsi', indicators.get('RSI_14', 50))
        
        # OPTIMIZED: Regime Filter (Don't fade strong trends)
        hurst = 0.5
        try:
             # Extract Hurst from mtf_data['analysis']['M15']['hurst'] if available
             hurst = mtf_data.get('analysis', {}).get('M15', {}).get('hurst', 0.5)
        except:
             pass
             
        if hurst > 0.6:
             return {'action': 'HOLD', 'confidence': 0, 'sl': 0, 'tp': 0, 'reason': f"Hurst {hurst:.2f} (Trending) - Unsafe for MeanRev"}
        
        # Logic: Buy Low, Sell High
        if rsi < self.lower:
            return {'action': 'BUY', 'confidence': 0.8, 'sl': df.iloc[-1]['close']*0.995, 'tp': df.iloc[-1]['close']*1.01}
            
        if rsi > self.upper:
             return {'action': 'SELL', 'confidence': 0.8, 'sl': df.iloc[-1]['close']*1.005, 'tp': df.iloc[-1]['close']*0.99}
                
        return {'action': 'HOLD', 'confidence': 0, 'sl': 0, 'tp': 0}

class MACD_Cross(ShadowStrategy):
    """
    MACD Momentum Strategy (The Flow).
    Logic:
        LONG: MACD Line > Signal Line.
        SHORT: MACD Line < Signal Line.
    """
    def __init__(self, direction="BOTH", speed="STD"):
        name = f"MACD_Cross_{direction}_{speed}"
        super().__init__(name, direction)
        self.speed = speed # Just for naming, uses pre-calc 'macd' and 'macd_signal'

    def _generate_raw_signal(self, df, indicators, mtf_data):
        # Note: MarketSensor provides 'macd' and 'macd_signal' (12,26,9) standard
        
        macd_line = indicators.get('macd', indicators.get('MACD', 0))
        signal_line = indicators.get('macd_signal', indicators.get('MACDs', 0))
        
        current_price = df.iloc[-1]['close']
        
        # Crossover logic
        if macd_line > signal_line:
             return {'action': 'BUY', 'confidence': 0.85, 'sl': current_price*0.995, 'tp': current_price*1.01}
             
        if macd_line < signal_line:
            return {'action': 'SELL', 'confidence': 0.85, 'sl': current_price*1.005, 'tp': current_price*0.99}
                
        return {'action': 'HOLD', 'confidence': 0, 'sl': 0, 'tp': 0}

class TrendPullback(ShadowStrategy):
    """
    4. The 'Tactician': Buying Pullbacks in a defined Trend.
    Logic:
        LONG: Price > EMA200 (Trend) AND Price touches EMA20/50 (Value) AND RSI Not Overbought.
    """
    def _generate_raw_signal(self, df, indicators, mtf_data):
        current_price = df.iloc[-1]['close']
        
        # 1. Trend Filter (Must be established)
        ema_200 = indicators.get('ema_200', indicators.get('EMA_200', 0))
        if ema_200 == 0: return {'action': 'HOLD', 'confidence': 0, 'sl': 0, 'tp': 0}
        
        # 2. Value Zones
        ema_50 = indicators.get('ema_50', indicators.get('EMA_50', 0))
        # ema_20 not standard in Sensor, estimate or use close proxy for now? 
        # Actually, let's use EMA 50 as the main "Value Zone" as it is robust.
        
        rsi = indicators.get('rsi', indicators.get('RSI_14', 50))
        
        # LONG SETUP
        if current_price > ema_200:
            # Pullback Condition: Price is close to EMA 50 (within 0.2%) OR has dipped below it recently
            # Simple check: Price < EMA 50 * 1.002 (Touching or below)
            # But must be > EMA 200 (Trend is up)
            if current_price <= (ema_50 * 1.002) and current_price > ema_200:
                # Validation: RSI not crashed (<30 bad, >70 bad). Ideal 35-55.
                if 35 < rsi < 60:
                     # Stop Loss: Recent Low or fixed ATR. Let's use 1.5% fixed for robustness
                     sl = current_price * 0.985
                     tp = current_price * 1.03 # 1:2 R:R
                     return {'action': 'BUY', 'confidence': 0.85, 'sl': sl, 'tp': tp, 'reason': "EMA50 Pullback (Trend Up)"}
                     
        # SHORT SETUP
        elif current_price < ema_200:
            if current_price >= (ema_50 * 0.998) and current_price < ema_200:
                 if 40 < rsi < 65:
                     sl = current_price * 1.015
                     tp = current_price * 0.97
                     return {'action': 'SELL', 'confidence': 0.85, 'sl': sl, 'tp': tp, 'reason': "EMA50 Pullback (Trend Down)"}

        return {'action': 'HOLD', 'confidence': 0, 'sl': 0, 'tp': 0}

class DarwinEngine:
    def __init__(self):
        self.strategies = []
        self.state_file = os.path.join(Config.BASE_DIR, "darwin_state.json")
        
        # === PROJECT HIVE: SWARM GENERATION (54 Variants) ===
        
        # 1. TrendHawks (Fibonacci Sequence)
        # 8 Periods * 2 Directions = 16 Variants
        periods = [9, 13, 21, 34, 55, 89, 144, 200]
        for p in periods:
            self.strategies.append(TrendHawk(f"TrendHawk_LONG_{p}p", direction="LONG", params={'period': p}))
            self.strategies.append(TrendHawk(f"TrendHawk_SHORT_{p}p", direction="SHORT", params={'period': p}))
            
        # 2. MeanReverters (Standard Deviations)
        # 5 Deviations * 2 Directions = 10 Variants
        devs = [1.5, 2.0, 2.5, 3.0, 3.5]
        for d in devs:
            lbl = f"{d:.1f}SD"
            self.strategies.append(MeanReverter(f"MeanRev_LONG_{lbl}", direction="LONG", params={'std_dev': d}))
            self.strategies.append(MeanReverter(f"MeanRev_SHORT_{lbl}", direction="SHORT", params={'std_dev': d}))
            
        # 3. RSI Matrix (Boundaries)
        # 5 Settings * 2 Directions = 10 Variants
        # (Lower, Upper) tuples
        rsi_settings = [
            (30, 70), (25, 75), (20, 80), (15, 85), (10, 90)
        ]
        for low, high in rsi_settings:
            self.strategies.append(RSI_Matrix(lower=low, upper=high, direction="LONG"))
            self.strategies.append(RSI_Matrix(lower=low, upper=high, direction="SHORT"))

        # 4. MACD Cross (Momentum)
        # 2 Variants (Standard Speed 12/26/9)
        # In future, can expand speed logic if MarketSensor supports custom MACD
        self.strategies.append(MACD_Cross(direction="LONG", speed="STD"))
        self.strategies.append(MACD_Cross(direction="SHORT", speed="STD"))
        
        # 5. The Sniper (Expert)
        # 1 Variant
        self.strategies.append(Sniper("Sniper_Elite", direction='BOTH'))
        
        # 6. TrendPullback (The Gap Filler)
        # 2 Variants (Standard)
        self.strategies.append(TrendPullback("TrendPullback_LONG", direction="LONG"))
        self.strategies.append(TrendPullback("TrendPullback_SHORT", direction="SHORT"))
        
        print(f"🐝 Darwin Swarm Initialized: {len(self.strategies)} Active Strategies.")
        
        # LOAD BRAIN MEMORY
        self.load_state()
        
        if self.strategies:
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
        """
        Retrieves signal from the active leader.
        Supports 'Allowed Strategies' filter from BIF Brain (Scout Protocol).
        """
        # 1. Get Restrictions
        bif_analysis = mtf_data.get('analysis', {})
        allowed = bif_analysis.get('allowed_strategies', ['ALL'])
        
        # 2. Select Strategy
        selected_strat = self.leader # Default to Global Leader
        
        if 'ALL' not in allowed:
            # We are in restricted mode (e.g. Scout Protocol)
            # Find the highest scoring strategy that matches the allow list
            found = False
            for strat in self.strategies:
                # Check match (e.g. "MeanReverter_LONG" in allowed matches "MeanRev_LONG_2.0SD")
                # Need to be careful with naming conventions.
                # Convention:
                # BIF Output: "MeanReverter_LONG", "RSI_Matrix_LONG"
                # Strat Names: "MeanRev_LONG_...", "RSI_Matrix_LONG_..."
                
                # Normalize for matching
                is_match = False
                for allow_tag in allowed:
                    # Map BIF tag to Strat Name substring
                    tag_map = {
                        "MeanReverter_LONG": "MeanRev_LONG",
                        "MeanReverter_SHORT": "MeanRev_SHORT",
                        "RSI_Matrix_LONG": "RSI_Matrix_LONG", 
                        "RSI_Matrix_SHORT": "RSI_Matrix_SHORT",
                        "TrendHawk_LONG": "TrendHawk_LONG",
                        "TrendHawk_SHORT": "TrendHawk_SHORT"
                    }
                    search_term = tag_map.get(allow_tag, allow_tag)
                    if search_term in strat.name:
                        is_match = True
                        break
                
                if is_match:
                    selected_strat = strat
                    found = True
                    break
            
            if not found:
                return {'action': 'HOLD', 'reason': 'No strategies fit Regime Restrictions'}

        # 3. Generate Signal
        signal = selected_strat.generate_signal(df, indicators, mtf_data)
        signal['source'] = f"Darwin::{selected_strat.name}"
        signal['darwin_score'] = self.last_scores.get(selected_strat.name, 0)
        
        # 4. Inject Scout Metadata if restricted
        if 'ALL' not in allowed:
            signal['scout_mode'] = True
            
        return signal

    def get_consensus_signal(self, df, indicators, mtf_data, top_n=3) -> dict:
        """
        Phase 93: The Jury.
        Instead of following 1 leader, we poll the Top N strategies.
        Returns a consensus signal.
        """
        # 1. Reuse Filtering Logic from get_alpha_signal
        bif_analysis = mtf_data.get('analysis', {})
        allowed = bif_analysis.get('allowed_strategies', ['ALL'])
        
        candidates = []
        
        # Filter Logic
        if 'ALL' in allowed:
            candidates = self.strategies # Already sorted by score
        else:
            # Filter specifically
            for strat in self.strategies:
                 is_match = False
                 for allow_tag in allowed:
                    tag_map = {
                        "MeanReverter_LONG": "MeanRev_LONG",
                        "MeanReverter_SHORT": "MeanRev_SHORT",
                        "RSI_Matrix_LONG": "RSI_Matrix_LONG", 
                        "RSI_Matrix_SHORT": "RSI_Matrix_SHORT",
                        "TrendHawk_LONG": "TrendHawk_LONG",
                        "TrendHawk_SHORT": "TrendHawk_SHORT"
                    }
                    search_term = tag_map.get(allow_tag, allow_tag)
                    if search_term in strat.name:
                        is_match = True
                        break
                 if is_match:
                     candidates.append(strat)
        
        # If not enough candidates, take what we have
        if not candidates:
             return {'action': 'HOLD', 'reason': 'No Available Candidates for Jury'}
             
        # UPDATED: FORCE DIVERSITY - Select cross-strategy jury
        # Pick 1 Trend + 1 Mean Reversion + 1 Momentum for balanced perspective
        jury = []
        strategy_types = ["TrendHawk", "MeanRev", "RSI_Matrix", "MACD_Cross", "Sniper"]
        
        for strategy_type in strategy_types:
            for strat in candidates:
                if strategy_type in strat.name and strat not in jury:
                    jury.append(strat)
                    break
            if len(jury) >= top_n:
                break
        
        # Fallback: if diversity selection didn't get enough, fill from candidates
        if len(jury) < top_n:
            for strat in candidates:
                if strat not in jury:
                    jury.append(strat)
                if len(jury) >= top_n:
                    break
        
        # Final fallback: just take top N if still not enough
        if len(jury) == 0:
            jury = candidates[:top_n]
            
        # === ROOKIE PROTECTION / SCOUT PROTOCOL ===
        # If we have a new strategy with 0 trades, it will never get picked if score is low.
        # We must FORCE it into the Jury occasionally to test it.
        # Logic: 20% chance to swap the lowest scoring Juror with a Rookie (0 trades)
        import random
        if random.random() < 0.25: # 25% Chance per tick
             rookies = [s for s in candidates if s.win_streak == 0 and s.loss_streak == 0 and s.name not in [j.name for j in jury]]
             if rookies:
                 rookie = random.choice(rookies)
                 # Remove lowest scoring member of current jury
                 if jury:
                     # Sort jury by score temporarily to find weakest link
                     jury.sort(key=lambda s: self.last_scores.get(s.name, 0))
                     removed = jury.pop(0) # Remove weakest
                     jury.append(rookie)
                     print(f"🕵️ SCOUT PROTOCOL: Swapped {removed.name} for Rookie {rookie.name}")
        
        votes = {'BUY': 0, 'SELL': 0, 'HOLD': 0}
        reasons = []
        
        print(f"⚖️ THE JURY IS IN SESSION. Members: {[s.name for s in jury]}")
        
        for juror in jury:
            sig = juror.generate_signal(df, indicators, mtf_data)
            action = sig['action']
            votes[action] = votes.get(action, 0) + 1
            # ENHANCED LOGGING: Show the reason!
            reason_stub = sig.get('reason', 'No Signal')
            reasons.append(f"{juror.name}: {action} [{reason_stub}]")
            
        # Decision Logic
        final_action = "HOLD"
        confidence = 0.0
        details = " | ".join(reasons)
        
        # Check Unanimous
        if votes['BUY'] == len(jury):
            final_action = "BUY"
            confidence = 1.0
            details = f"UNANIMOUS BUY ({details})"
        elif votes['SELL'] == len(jury):
            final_action = "SELL"
            confidence = 1.0
            details = f"UNANIMOUS SELL ({details})"
            
        # UPDATED: Reduced Quorum - Allow single strong signal
        # Check Majority (2+ votes)
        elif votes['BUY'] >= 2:
             final_action = "BUY"
             # Scale confidence: 2/3 = 0.73, 3/3 = 0.80
             confidence = 0.6 + (votes['BUY'] / len(jury) * 0.2)
             details = f"MAJORITY BUY ({details})"
        elif votes['SELL'] >= 2:
             final_action = "SELL"
             confidence = 0.6 + (votes['SELL'] / len(jury) * 0.2)
             details = f"MAJORITY SELL ({details})"
        
        # NEW: Partial Agreement (1 vote) - LONE WOLF MODE
        # In Scalping Mode (M5), speed > consensus. If one reliable strategy triggers, we take it.
        # But we use lower confidence score.
        elif votes['BUY'] >= 1:
            final_action = "BUY"
            confidence = 0.55  # Just enough to pass RiskManager (0.50 cutoff)
            details = f"LONE WOLF BUY ({details})"
        elif votes['SELL'] >= 1:
            final_action = "SELL"
            confidence = 0.55
            details = f"LONE WOLF SELL ({details})"
        
        else:
             final_action = "HOLD"
             details = f"HUNG JURY ({details})"
             
        # Inject Scout Metadata logic (reused)
        scout_mode = False
        if 'ALL' not in allowed:
            scout_mode = True

        return {
            'action': final_action,
            'confidence': confidence,
            'reason': details,
            'source': f"Jury::{len(jury)}",
            'darwin_score': self.last_scores.get(self.leader.name, 0), # Fallback score
            'scout_mode': scout_mode,
            'jury_votes': votes
        }

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
