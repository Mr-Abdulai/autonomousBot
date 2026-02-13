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

    @abstractmethod
    def clone(self, new_params: dict = None) -> 'ShadowStrategy':
        """Creates a new instance of this strategy with potentially mutated parameters."""
        pass
        
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
            hurst = mtf_regime.get('BASE', {}).get('hurst', 0.5)
            
            # Boost logic needs to check Class Name string AND Direction
            regime_trend = mtf_regime.get('trend', 'NEUTRAL') # Expecting 'BULLISH', 'BEARISH', 'RANGING'
            
            # GOLD OPTIMIZED: Favor trend strategies more aggressively
            # A. TREND STRATEGIES (TrendHawk, MACD_Cross, Sniper)
            is_trend_strat = any(x in self.name for x in ["TrendHawk", "MACD_Cross", "Sniper"])
            if is_trend_strat:
                if hurst > 0.55: # Trending Regime - GOLD LOVES THIS
                    # Directional Matching with HIGHER boost for Gold
                    if 'BULLISH' in regime_trend:
                        if self.direction == 'LONG' or self.direction == 'BOTH': boost = 1.5  # Gold: 1.5x vs 1.3x forex
                        elif self.direction == 'SHORT': boost = 0.6  # Penalize counter-trend harder
                    elif 'BEARISH' in regime_trend:
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
        
        # 3. Hot Hand Bonus (Speed of Adaptation)
        # Accelerate promotion of strategies that are winning RIGHT NOW.
        streak_bonus = 1.0
        if self.win_streak >= 2: streak_bonus = 1.10 # +10%
        if self.win_streak >= 3: streak_bonus = 1.25 # +25%
        if self.win_streak >= 5: streak_bonus = 1.50 # +50% (On Fire)
        
        final_score = (base_score * boost * streak_bonus) / penalty
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
        
        # BUY LOGIC
        if (self.direction in ['LONG', 'BOTH']) and is_bullish_trend:
            # Bullish Breakout
            if current_price >= high_x:
                p_sl = low_x 
                risk = current_price - p_sl
                if risk <= 0: return {'action': 'HOLD', 'confidence': 0, 'sl': 0, 'tp': 0, 'reason': 'Zero Risk Distance'}
                return {'action': 'BUY', 'confidence': 0.85, 'sl': p_sl, 'tp': current_price + 2*risk, 'reason': f'Breakout above {period}p High'}
                
        # SELL LOGIC
        if (self.direction in ['SHORT', 'BOTH']) and is_bearish_trend:
            # Bearish Breakout
            if current_price <= low_x:
                p_sl = high_x 
                risk = p_sl - current_price
                if risk <= 0: return {'action': 'HOLD', 'confidence': 0, 'sl': 0, 'tp': 0, 'reason': 'Zero Risk Distance'}
                return {'action': 'SELL', 'confidence': 0.85, 'sl': p_sl, 'tp': current_price - 2*risk, 'reason': f'Breakout below {period}p Low'}

        return {'action': 'HOLD', 'confidence': 0.0, 'sl': 0, 'tp': 0, 'reason': "No Breakout"}

    def clone(self, new_params: dict = None) -> 'TrendHawk':
        params = new_params if new_params else self.params.copy()
        p = params.get('period', 20)
        # Construct new name based on params
        new_name = f"TrendHawk_{self.direction}_{p}p"
        return TrendHawk(new_name, self.direction, params)

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
        if close > my_upper and rsi > 60:
            # OPTIMIZED: Target Basis (SMA20) not EMA50 (too far)
            return {'action': 'SELL', 'confidence': 0.75, 'sl': close * 1.002, 'tp': basis, 'reason': f'BB Fade High ({user_std}SD)'}
            
        # Fade Lows (Buy at Bottom of Range)
        if close < my_lower and rsi < 40:
            # OPTIMIZED: Target Basis
            return {'action': 'BUY', 'confidence': 0.75, 'sl': close * 0.998, 'tp': basis, 'reason': f'BB Fade Low ({user_std}SD)'}
            
        return {'action': 'HOLD', 'confidence': 0.0, 'sl': 0, 'tp': 0, 'reason': "Inside Bands"}

    def clone(self, new_params: dict = None) -> 'MeanReverter':
        params = new_params if new_params else self.params.copy()
        d = params.get('std_dev', 2.0)
        new_name = f"MeanRev_{self.direction}_{d:.1f}SD"
        return MeanReverter(new_name, self.direction, params)

class Sniper(ShadowStrategy):
    """
    3. The 'Perfectionist': Only trades if multiple Timeframes align.
    """
    def _generate_raw_signal(self, df: pd.DataFrame, indicators: dict, mtf_data: dict) -> dict:
         # FIX: Use Generic HTF1 key (supports H1 or M15)
         if 'HTF1' not in mtf_data or mtf_data['HTF1'].empty:
             return {'action': 'HOLD', 'confidence': 0, 'sl': 0, 'tp': 0}
             
         h1_df = mtf_data['HTF1']
         h1_close = h1_df.iloc[-1]['close']
         h1_ma = h1_df['close'].rolling(50).mean().iloc[-1] # Simple HTF Trend (M15/H1)
         
         current_price = df.iloc[-1]['close']
         # FIX: Shift(1) here too
         high_20 = df['high'].shift(1).rolling(20).max().iloc[-1]
         low_20 = df['low'].shift(1).rolling(20).min().iloc[-1]
         ema_50 = indicators.get('ema_50', indicators.get('EMA_50', 0))
         
         # ... (Rest of logic similar to TrendHawk but checking HTF1)
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
             
         # MATCH DASHBOARD LOGIC (EMA 13/50 Cross)
         h1_ema13 = h1_df['close'].ewm(span=13, adjust=False).mean().iloc[-1]
         h1_ema50 = h1_df['close'].ewm(span=50, adjust=False).mean().iloc[-1]
         
         is_h1_bullish = h1_ema13 > h1_ema50
         is_h1_bearish = h1_ema13 < h1_ema50
              
         if action == 'BUY':
             if is_h1_bullish:
                 return {'action': 'BUY', 'confidence': 0.95, 'sl': sl, 'tp': tp}
         elif action == 'SELL':
             if is_h1_bearish:
                 return {'action': 'SELL', 'confidence': 0.95, 'sl': sl, 'tp': tp}
        
         if action == "HOLD":
             return {'action': 'HOLD', 'confidence': 0.0, 'sl': 0, 'tp': 0, 'reason': f"No {self.name} PA Setup ({current_price:.5f} vs H:{high_20:.5f}/L:{low_20:.5f})"}
                 
         return {'action': 'HOLD', 'confidence': 0.0, 'sl': 0, 'tp': 0, 'reason': f"HTF1 Alignment Fail (Base={action}, HTF1_EMA13={h1_ema13:.5f}/EMA50={h1_ema50:.5f})"}

    def clone(self, new_params: dict = None) -> 'Sniper':
        return Sniper(self.name, self.direction)

class RSI_Matrix(ShadowStrategy):
    """
    RSI Mean Reversion Strategy (The Scalper).
    Logic:
        LONG: RSI < LowerBound (Oversold).
        SHORT: RSI > UpperBound (Overbought).
    """
    def __init__(self, name: str, direction: str = 'BOTH', params: dict = None):
        super().__init__(name, direction, params)
        self.lower = self.params.get('lower', 30)
        self.upper = self.params.get('upper', 70)

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
            return {'action': 'BUY', 'confidence': 0.8, 'sl': df.iloc[-1]['close']*0.995, 'tp': df.iloc[-1]['close']*1.01, 'reason': f'RSI Oversold ({rsi:.1f} < {self.lower})'}
            
        if rsi > self.upper:
             return {'action': 'SELL', 'confidence': 0.8, 'sl': df.iloc[-1]['close']*1.005, 'tp': df.iloc[-1]['close']*0.99, 'reason': f'RSI Overbought ({rsi:.1f} > {self.upper})'}
                
        return {'action': 'HOLD', 'confidence': 0, 'sl': 0, 'tp': 0, 'reason': f'RSI Neutral ({rsi:.1f})'}

    def clone(self, new_params: dict = None) -> 'RSI_Matrix':
        params = new_params if new_params else self.params.copy()
        l = params.get('lower', 30)
        u = params.get('upper', 70)
        new_name = f"RSI_Matrix_{self.direction}_{l}_{u}"
        return RSI_Matrix(new_name, self.direction, params)

class MACD_Cross(ShadowStrategy):
    """
    MACD Momentum Strategy (The Flow).
    Logic:
        LONG: MACD Line > Signal Line.
        SHORT: MACD Line < Signal Line.
    """
    def __init__(self, name: str, direction: str = 'BOTH', params: dict = None):
        super().__init__(name, direction, params)
        self.speed = self.params.get('speed', 'STD') 

    def _generate_raw_signal(self, df, indicators, mtf_data):
        # Note: MarketSensor provides 'macd' and 'macd_signal' (12,26,9) standard
        
        if self.speed == 'FAST':
            # Fast MACD (6, 13, 4)
            macd_line = indicators.get('macd_fast', indicators.get('MACD_Fast', 0))
            signal_line = indicators.get('macd_signal_fast', indicators.get('MACDs_Fast', 0))
        else:
            # Standard MACD (12, 26, 9)
            macd_line = indicators.get('macd', indicators.get('MACD', 0))
            signal_line = indicators.get('macd_signal', indicators.get('MACDs', 0))
        
        current_price = df.iloc[-1]['close']
        
        # Crossover logic
        if macd_line > signal_line:
             speed_label = 'Fast' if self.speed == 'FAST' else 'Std'
             return {'action': 'BUY', 'confidence': 0.85, 'sl': current_price*0.995, 'tp': current_price*1.01, 'reason': f'MACD Cross Up ({speed_label})'}
             
        if macd_line < signal_line:
             speed_label = 'Fast' if self.speed == 'FAST' else 'Std'
             return {'action': 'SELL', 'confidence': 0.85, 'sl': current_price*1.005, 'tp': current_price*0.99, 'reason': f'MACD Cross Down ({speed_label})'}
                
        return {'action': 'HOLD', 'confidence': 0, 'sl': 0, 'tp': 0, 'reason': 'No Crossover'}

    def clone(self, new_params: dict = None) -> 'MACD_Cross':
        params = new_params if new_params else self.params.copy()
        speed = params.get('speed', 'STD')
        new_name = f"MACD_Cross_{self.direction}_{speed}"
        return MACD_Cross(new_name, self.direction, params)

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
        if ema_200 == 0: return {'action': 'HOLD', 'confidence': 0, 'sl': 0, 'tp': 0, 'reason': 'No EMA200 data'}
        
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

        return {'action': 'HOLD', 'confidence': 0, 'sl': 0, 'tp': 0, 'reason': 'No Pullback Setup'}

    def clone(self, new_params: dict = None) -> 'TrendPullback':
        return TrendPullback(self.name, self.direction)

class DarwinEngine:
    def __init__(self):
        self.strategies = []
        self.state_file = os.path.join(Config.BASE_DIR, "darwin_state.json")
        
        # === PROJECT HIVE: SWARM GENERATION (SHARPER EDITION) ===
        
        # 1. TrendHawks (Fibonacci Sequence - Optimized for M15)
        # Removed 9/13 (Too Noisy) and 200 (Too Laggy). Focus on medium-term trend.
        periods = [21, 34, 55, 89, 144] 
        for p in periods:
            self.strategies.append(TrendHawk(f"TrendHawk_LONG_{p}p", direction="LONG", params={'period': p}))
            self.strategies.append(TrendHawk(f"TrendHawk_SHORT_{p}p", direction="SHORT", params={'period': p}))
            
        # 2. MeanReverters (Standard Deviations - Sharper Entries)
        # Removed 1.0/1.5 SD (Too Loose). Added 3.5 SD (Extreme Reversion).
        devs = [2.0, 2.5, 3.0, 3.5]
        for d in devs:
            lbl = f"{d:.1f}SD"
            self.strategies.append(MeanReverter(f"MeanRev_LONG_{lbl}", direction="LONG", params={'std_dev': d}))
            self.strategies.append(MeanReverter(f"MeanRev_SHORT_{lbl}", direction="SHORT", params={'std_dev': d}))
            
        # 3. RSI Matrix (Boundaries - Tighter Extremes)
        # Removed 30/70 (Standard). Focused on 25/75 and tighter.
        rsi_settings = [
            (25, 75), (20, 80), (15, 85), (10, 90)
        ]
        for low, high in rsi_settings:
            p = {'lower': low, 'upper': high}
            self.strategies.append(RSI_Matrix(f"RSI_{low}_{high}_LONG", direction="LONG", params=p))
            self.strategies.append(RSI_Matrix(f"RSI_{low}_{high}_SHORT", direction="SHORT", params=p))

        # 4. MACD Cross (Momentum - Multi-Speed)
        # Added FAST variant (6, 13, 4) for quicker scalps on M15
        self.strategies.append(MACD_Cross("MACD_Cross_LONG_STD", direction="LONG", params={'speed': 'STD'}))
        self.strategies.append(MACD_Cross("MACD_Cross_SHORT_STD", direction="SHORT", params={'speed': 'STD'}))
        
        self.strategies.append(MACD_Cross("MACD_Cross_LONG_FAST", direction="LONG", params={'speed': 'FAST'}))
        self.strategies.append(MACD_Cross("MACD_Cross_SHORT_FAST", direction="SHORT", params={'speed': 'FAST'}))
        
        # 5. The Sniper (Expert)
        # 1 Variant
        self.strategies.append(Sniper("Sniper_Elite", direction='BOTH'))
        
        # 6. TrendPullback (The Gap Filler)
        # 2 Variants (Standard) — FIX: Removed duplicate registration
        self.strategies.append(TrendPullback("TrendPullback_LONG", direction="LONG"))
        self.strategies.append(TrendPullback("TrendPullback_SHORT", direction="SHORT"))
        
        print(f"🐝 Darwin Swarm Initialized: {len(self.strategies)} Active Strategies.")
        
        # LOAD BRAIN MEMORY
        self.load_state()
        
        if self.strategies:
            self.leader = self.strategies[0]
        self.last_scores = {}
        
    def _get_strategy_class(self, class_name):
        """Helper to map string name to class object."""
        mapping = {
            'TrendHawk': TrendHawk,
            'MeanReverter': MeanReverter,
            'RSI_Matrix': RSI_Matrix,
            'MACD_Cross': MACD_Cross,
            'Sniper': Sniper,
            'TrendPullback': TrendPullback
        }
        return mapping.get(class_name)
        
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
            if last_save_time:
                try:
                    save_dt = datetime.fromisoformat(last_save_time)
                    hours_old = (datetime.now() - save_dt).total_seconds() / 3600
                    if hours_old > 1.0: # Stale after 1 hour
                        print(f"🧠 Memory is Stale ({hours_old:.1f}h). Applying HEAVY DECAY (50%).")
                        decay_factor = 0.5
                    else:
                        decay_factor = 0.95
                except:
                    pass

            if 'population' in data:
                # NEW FORMAT: Full Reconstruction (Preserves Mutations)
                print("🧬 Loading Advanced Darwin State (Population Rehydration)...")
                restored_strats = []
                
                for s_data in data['population']:
                    try:
                        cls_name = s_data.get('class')
                        StratClass = self._get_strategy_class(cls_name)
                        if not StratClass: continue
                        
                        # Re-instantiate
                        name = s_data.get('name')
                        direction = s_data.get('direction', 'BOTH')
                        params = s_data.get('params', {})
                        
                        # Instantiate Strategy
                        strat = StratClass(name, direction=direction, params=params)
                        
                        # Restore Metrics
                        metrics = s_data.get('metrics', {})
                        raw_equity = metrics.get('equity', 10000.0)
                        
                        # Apply Decay
                        pnl = raw_equity - 10000.0
                        strat.phantom_equity = 10000.0 + (pnl * decay_factor)
                        strat.peak_equity = max(10000.0, strat.phantom_equity)
                        strat.max_drawdown = metrics.get('dd', 0.0) * decay_factor
                        strat.win_streak = metrics.get('wins', 0) if decay_factor >= 1.0 else 0
                        strat.loss_streak = metrics.get('losses', 0) if decay_factor >= 1.0 else 0
                        
                        restored_strats.append(strat)
                    except Exception as e:
                        print(f"Failed to restore specific strategy {s_data.get('name', 'Unknown')}: {e}")
                        
                if restored_strats:
                    self.strategies = restored_strats
                    print(f"🧬 Successfully restored {len(self.strategies)} strategies from disk.")
                else:
                    print("⚠️ Failed to restore strategies. Using default population.")
                    
            else:
                # LEGACY FORMAT: Partial Restore (Only metrics for matching names)
                print("🧬 Loading Legacy Darwin State (Metrics Only)...")
                
                for strat in self.strategies:
                    if strat.name in data:
                        s_data = data[strat.name]
                        # Restore Stats
                        raw_equity = s_data.get('equity', 10000.0)
                        
                        # Apply Decay to PnL (Normalize towards 10k)
                        pnl = raw_equity - 10000.0
                        strat.phantom_equity = 10000.0 + (pnl * decay_factor)
                        
                        strat.peak_equity = max(10000.0, strat.phantom_equity)
                        strat.max_drawdown = s_data.get('dd', 0.0) * decay_factor
                        
                        if decay_factor < 1.0:
                            strat.win_streak = 0
                            strat.loss_streak = 0
                        else:
                            strat.win_streak = s_data.get('wins', 0)
                            strat.loss_streak = s_data.get('losses', 0)
                            
                print(f"🧬 Legacy Memory Loaded.")

        except Exception as e:
            print(f"Darwin Memory Load Error: {e}")

    def save_state(self):
        """
        Persists evolution history (Full Population) to disk.
        Saves: Name, Class, Params, Metrics to ensure Mutations survive restart.
        """
        population_data = []
        for strat in self.strategies:
            # Handle class name retrieval
            cls_name = strat.__class__.__name__
            
            population_data.append({
                'name': strat.name,
                'class': cls_name,
                'direction': strat.direction,
                'params': strat.params,
                'metrics': {
                    'equity': strat.phantom_equity,
                    'peak': strat.peak_equity,
                    'dd': strat.max_drawdown,
                    'wins': strat.win_streak,
                    'losses': strat.loss_streak
                }
            })
            
        data = {
            'timestamp': datetime.now().isoformat(),
            'version': '2.0',
            'population': population_data
        }
        
        try:
            # Atomic write pattern
            temp = self.state_file + ".tmp"
            with open(temp, 'w') as f:
                json.dump(data, f, indent=4)
            
            if os.path.exists(self.state_file):
                os.remove(self.state_file)
            os.rename(temp, self.state_file)
            
        except Exception as e:
            print(f"Darwin Save Error: {e}")

    def report_execution(self, signal: dict, result: str):
        """
        Feedback loop from main.py.
        Called when a trade is BLOCKED by Risk Manager or Chronos.
        Penalizes the source strategy so Darwin can learn.
        """
        source = signal.get('source', '')
        
        if result == 'BLOCKED':
            # Find the strategy that generated this signal
            for strat in self.strategies:
                if strat.name in source:
                    # Penalize: Count as a loss (small penalty)
                    strat.loss_streak += 1
                    strat.win_streak = 0
                    print(f"🧬 Darwin Feedback: {strat.name} penalized (Signal BLOCKED).")
                    break

    def update(self, df: pd.DataFrame, indicators: dict, mtf_data: dict):
        current_price = df.iloc[-1]['close']
        regime_context = mtf_data.get('analysis', {}) 
        
        # FIX (Flaw 8): Cache signals to avoid double generation in consensus
        self._cached_signals = {}
        
        for strat in self.strategies:
            strat.update_performance(current_price)
            if not strat.active_trade:
                signal = strat.generate_signal(df, indicators, mtf_data)
                self._cached_signals[strat.name] = signal  # Cache for reuse
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
                    # FIX (Flaw 6): Complete tag map matching BIF tags → actual strategy name patterns
                    # Each value is a list of substrings that ALL must appear in strat.name
                    tag_map = {
                        "MeanReverter_LONG": ["MeanRev_LONG"],
                        "MeanReverter_SHORT": ["MeanRev_SHORT"],
                        "RSI_Matrix_LONG": ["RSI_", "_LONG"],  # RSI_25_75_LONG
                        "RSI_Matrix_SHORT": ["RSI_", "_SHORT"],  # RSI_25_75_SHORT
                        "TrendHawk_LONG": ["TrendHawk_LONG"],
                        "TrendHawk_SHORT": ["TrendHawk_SHORT"],
                        "TrendPullback_LONG": ["TrendPullback_LONG"],
                        "TrendPullback_SHORT": ["TrendPullback_SHORT"],
                        "MACD_Cross_LONG": ["MACD_Cross_LONG"],
                        "MACD_Cross_SHORT": ["MACD_Cross_SHORT"],
                        "Sniper_Elite": ["Sniper_Elite"]
                    }
                    search_terms = tag_map.get(allow_tag, [allow_tag])
                    if all(term in strat.name for term in search_terms):
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

    def evolve_population(self):
        """
        GENETIC ALGORITHM: DAILY EVOLUTION EVENT
        1. Select Elites (Top 20%) - They survive.
        2. Cull Weakest (Bottom 20%) - They die.
        3. Breed/Mutate Middle Class - They evolve.
        4. EXTINCTION PROTECTION - Ensure minimum species diversity.
        """
        # Hard Cap to prevent explosion
        MAX_POPULATION = 100
        
        # Sort by Score
        self.strategies.sort(key=lambda s: s.get_quality_score(), reverse=True)
        count = len(self.strategies)
        
        # 1. ELITISM
        n_elites = max(5, int(count * 0.2))
        elites = self.strategies[:n_elites]
        print(f"🧬 EVOLUTION: {n_elites} Elites moved to next generation.")
        
        # 2. CULLING
        n_cull = max(5, int(count * 0.2))
        survivors = self.strategies[:-n_cull] # Keep top 80% initially, but we will replace bottom
        
        # Actually, let's keep the Top 50% as Parents
        parent_pool = self.strategies[:int(count * 0.5)]
        
        next_gen = []
        next_gen.extend(elites) # Elites live forever (until dethroned)
        
        # Fill the rest of the slots
        slots_open = MAX_POPULATION - len(next_gen)
        
        import random
        
        while len(next_gen) < MAX_POPULATION:
            # Pick a parent
            parent = random.choice(parent_pool)
            
            # MUTATION (Create a variant)
            child = self.mutate(parent)
            
            # Verify Uniqueness (Simple Name Check)
            if not any(s.name == child.name for s in next_gen):
                next_gen.append(child)
            
            if len(next_gen) >= MAX_POPULATION:
                break
        
        # 4. EXTINCTION PROTECTION
        # Ensure at least 1 seed of each critical strategy type/direction survives.
        # Without this, evolution can kill entire species (MACD_Cross, Sniper, etc.)
        required_seeds = [
            # (class, name, direction, params)
            (TrendHawk,     "TrendHawk_LONG_55p",    "LONG",  {'period': 55}),
            (TrendHawk,     "TrendHawk_SHORT_55p",   "SHORT", {'period': 55}),
            (MeanReverter,  "MeanRev_LONG_2.5SD",    "LONG",  {'std_dev': 2.5}),
            (MeanReverter,  "MeanRev_SHORT_2.5SD",   "SHORT", {'std_dev': 2.5}),
            (MACD_Cross,    "MACD_Cross_LONG_FAST",  "LONG",  {'speed': 'FAST'}),
            (MACD_Cross,    "MACD_Cross_SHORT_FAST", "SHORT", {'speed': 'FAST'}),
            (RSI_Matrix,    "RSI_25_75_LONG",        "LONG",  {'lower': 25, 'upper': 75}),
            (RSI_Matrix,    "RSI_25_75_SHORT",       "SHORT", {'lower': 25, 'upper': 75}),
            (Sniper,        "Sniper_Elite",          "BOTH",  {}),
            (TrendPullback, "TrendPullback_LONG",    "LONG",  {}),
            (TrendPullback, "TrendPullback_SHORT",   "SHORT", {}),
        ]
        
        injected = 0
        for cls, name, direction, params in required_seeds:
            # Check if ANY strategy of this class+direction exists
            has_species = any(
                isinstance(s, cls) and s.direction == direction
                for s in next_gen
            )
            if not has_species:
                seed = cls(name, direction=direction, params=params)
                # Replace the weakest strategy to stay within population cap
                if len(next_gen) >= MAX_POPULATION:
                    next_gen[-1] = seed
                else:
                    next_gen.append(seed)
                injected += 1
                print(f"🛡️ EXTINCTION PROTECTION: Injected {name} (species was extinct!)")
        
        if injected > 0:
            print(f"🛡️ Protected {injected} endangered species from extinction.")
                
        self.strategies = next_gen
        print(f"🧬 EVOLUTION COMPLETE. Population: {len(self.strategies)}")

    def mutate(self, parent: ShadowStrategy) -> ShadowStrategy:
        """Applies random drift to strategy parameters."""
        import random
        
        # Determine Type and Mutate
        new_params = parent.params.copy()
        
        if isinstance(parent, TrendHawk):
            current_p = new_params.get('period', 20)
            # Drift +/- 10%
            drift = int(current_p * random.uniform(-0.2, 0.2)) 
            if drift == 0: drift = random.choice([-1, 1])
            new_p = max(5, current_p + drift)
            new_params['period'] = new_p
            return parent.clone(new_params)
            
        elif isinstance(parent, MeanReverter):
            current_std = new_params.get('std_dev', 2.0)
            drift = random.uniform(-0.2, 0.2)
            new_std = round(max(1.0, min(4.0, current_std + drift)), 1)
            new_params['std_dev'] = new_std
            return parent.clone(new_params)
            
        elif isinstance(parent, RSI_Matrix):
            # Special case for RSI (Attributes, not params dict)
            drift = random.randint(-5, 5)
            new_lower = max(10, min(45, parent.lower + drift))
            new_upper = max(55, min(90, parent.upper + drift))
            return parent.clone({'lower': new_lower, 'upper': new_upper})
            
        # Default (No mutation implemented for this type, clone exact)
        return parent.clone()

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
                    # FIX (Flaw 6): Complete tag map matching BIF tags → actual strategy name patterns
                    # Each value is a list of substrings that ALL must appear in strat.name
                    tag_map = {
                        "MeanReverter_LONG": ["MeanRev_LONG"],
                        "MeanReverter_SHORT": ["MeanRev_SHORT"],
                        "RSI_Matrix_LONG": ["RSI_", "_LONG"],
                        "RSI_Matrix_SHORT": ["RSI_", "_SHORT"],
                        "TrendHawk_LONG": ["TrendHawk_LONG"],
                        "TrendHawk_SHORT": ["TrendHawk_SHORT"],
                        "TrendPullback_LONG": ["TrendPullback_LONG"],
                        "TrendPullback_SHORT": ["TrendPullback_SHORT"],
                        "MACD_Cross_LONG": ["MACD_Cross_LONG"],
                        "MACD_Cross_SHORT": ["MACD_Cross_SHORT"],
                        "Sniper_Elite": ["Sniper_Elite"]
                    }
                    search_terms = tag_map.get(allow_tag, [allow_tag])
                    if all(term in strat.name for term in search_terms):
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

    def get_consensus_signal(self, df, indicators, mtf_data, top_n=5) -> dict:
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
                    # FIX (Flaw 6): Complete tag map matching BIF tags → actual strategy name patterns
                    # Each value is a list of substrings that ALL must appear in strat.name
                    tag_map = {
                        "MeanReverter_LONG": ["MeanRev_LONG"],
                        "MeanReverter_SHORT": ["MeanRev_SHORT"],
                        "RSI_Matrix_LONG": ["RSI_", "_LONG"],
                        "RSI_Matrix_SHORT": ["RSI_", "_SHORT"],
                        "TrendHawk_LONG": ["TrendHawk_LONG"],
                        "TrendHawk_SHORT": ["TrendHawk_SHORT"],
                        "TrendPullback_LONG": ["TrendPullback_LONG"],
                        "TrendPullback_SHORT": ["TrendPullback_SHORT"],
                        "MACD_Cross_LONG": ["MACD_Cross_LONG"],
                        "MACD_Cross_SHORT": ["MACD_Cross_SHORT"],
                        "Sniper_Elite": ["Sniper_Elite"]
                    }
                    search_terms = tag_map.get(allow_tag, [allow_tag])
                    if all(term in strat.name for term in search_terms):
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
        # FIX: Collect SL/TP from voters so consensus preserves strategy precision
        voter_signals = {'BUY': [], 'SELL': []}
        
        print(f"⚖️ THE JURY IS IN SESSION. Members: {[s.name for s in jury]}")
        
        for juror in jury:
            # FIX (Flaw 8): Reuse cached signal from update() if available
            sig = getattr(self, '_cached_signals', {}).get(juror.name) or juror.generate_signal(df, indicators, mtf_data)
            action = sig['action']
            votes[action] = votes.get(action, 0) + 1
            # ENHANCED LOGGING: Show the reason!
            reason_stub = sig.get('reason', 'No Signal')
            reasons.append(f"{juror.name}: {action} [{reason_stub}]")
            
            # Capture SL/TP from directional voters
            if action in ['BUY', 'SELL'] and sig.get('sl', 0) != 0:
                voter_signals[action].append({
                    'name': juror.name,
                    'sl': sig['sl'],
                    'tp': sig['tp'],
                    'confidence': sig.get('confidence', 0.5)
                })
            
        # Decision Logic
        final_action = "HOLD"
        confidence = 0.0
        details = " | ".join(reasons)
        
        # Check Unanimous
        # Updated Consensus Logic for Top 5
        buy_votes = votes['BUY']
        sell_votes = votes['SELL']
        total_votes = len(jury)
        
        # 1. UNANIMOUS (Strongest)
        if buy_votes == total_votes:
            final_action = "BUY"
            confidence = 1.0
            details = f"UNANIMOUS BUY ({details})"
        elif sell_votes == total_votes:
            final_action = "SELL"
            confidence = 1.0
            details = f"UNANIMOUS SELL ({details})"
            
        # 2. MAJORITY (More votes than opposition AND at least 2)
        elif buy_votes > sell_votes and buy_votes >= 2:
            final_action = "BUY"
            confidence = 0.6 + (buy_votes / total_votes * 0.3)
            details = f"MAJORITY BUY {buy_votes}v{sell_votes} ({details})"
        elif sell_votes > buy_votes and sell_votes >= 2:
            final_action = "SELL"
            confidence = 0.6 + (sell_votes / total_votes * 0.3)
            details = f"MAJORITY SELL {sell_votes}v{buy_votes} ({details})"
            
        # 3. TIE / CONFLICT (2v2) -> HOLD
        elif buy_votes == sell_votes and buy_votes >= 2:
            final_action = "HOLD"
            details = f"CONFLICT {buy_votes}v{sell_votes} ({details})"

        # 4. LONE WOLF (1 vote vs 0 opposition)
        # Scalping Mode: If 1 reliable leader sees it and others are asleep (HOLD), take it.
        # But if 1 says BUY and 1 says SELL, it's a conflict.
        elif buy_votes == 1 and sell_votes == 0:
            final_action = "BUY"
            confidence = 0.55
            details = f"LONE WOLF BUY ({details})"
        elif sell_votes == 1 and buy_votes == 0:
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

        # FIX: Extract best SL/TP from winning side (highest confidence voter)
        best_sl = 0
        best_tp = 0
        if final_action in ['BUY', 'SELL'] and voter_signals[final_action]:
            # Pick the voter with highest confidence for SL/TP
            best_voter = max(voter_signals[final_action], key=lambda v: v['confidence'])
            best_sl = best_voter['sl']
            best_tp = best_voter['tp']
            print(f"📐 Jury SL/TP from {best_voter['name']}: SL={best_sl:.5f}, TP={best_tp:.5f}")

        return {
            'action': final_action,
            'confidence': confidence,
            'reason': details,
            'source': f"Jury::{len(jury)}",
            'darwin_score': self.last_scores.get(self.leader.name, 0),
            'scout_mode': scout_mode,
            'jury_votes': votes,
            'sl': best_sl,
            'tp': best_tp
        }

    def get_leaderboard(self) -> str:
        # Hydra Upgrade: Only show Top 5 to avoid console spam
        s = "Darwin Smart Leaderboard (Top 5):\n"
        for i, strat in enumerate(self.strategies[:5]):
            score = self.last_scores.get(strat.name, 0)
            s += f" {i+1}. {strat.name}: Score {score:.0f} (Eq: ${strat.phantom_equity:.0f})\n"
        return s

    def get_swarm_state(self) -> dict:
        """Returns full state of all strategies for Dashboard (Aggregated)."""
        
        # 1. Aggregate by Family
        families = {}
        for s in self.strategies:
            # Extract Family Name (e.g. TrendHawk_LONG_20p -> TrendHawk)
            family_name = s.name.split('_')[0]
            
            if family_name not in families:
                families[family_name] = {
                    'count': 0,
                    'total_score': 0,
                    'best_score': -9999,
                    'best_agent': None,
                    'total_equity': 0,
                    'strategies': []
                }
            
            f = families[family_name]
            f['count'] += 1
            
            score = self.last_scores.get(s.name, 0)
            f['total_score'] += score
            f['total_equity'] += s.phantom_equity
            
            if score > f['best_score']:
                f['best_score'] = score
                f['best_agent'] = s.name
                
        # 2. Calculate Averages
        final_families = {}
        for fname, stats in families.items():
            avg_score = stats['total_score'] / stats['count'] if stats['count'] > 0 else 0
            final_families[fname] = {
                'count': stats['count'],
                'avg_score': avg_score,
                'best_agent': stats['best_agent'],
                'best_score': stats['best_score'],
                'equity': stats['total_equity']
            }

        # 3. Top Performers (Elite Leaderboard)
        # Sort by score
        sorted_strats = sorted(self.strategies, key=lambda s: self.last_scores.get(s.name, 0), reverse=True)
        top_performers = []
        for s in sorted_strats[:10]:
            top_performers.append({
                "name": s.name,
                "equity": s.phantom_equity,
                "score": self.last_scores.get(s.name, 0),
                "wins": s.win_streak,
                "losses": s.loss_streak,
                "dd": s.max_drawdown, # 'drawdown' in legacy, 'dd' in new UI? let's stick to 'dd' to match UI code
                "peak": s.peak_equity,
                "direction": s.direction
            })

        return {
            "families": final_families,
            "top_performers": top_performers,
            "population_size": len(self.strategies)
        }
