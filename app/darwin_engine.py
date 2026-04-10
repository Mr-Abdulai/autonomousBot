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
            sl = self.active_trade['sl']
            tp = self.active_trade['tp']
            
            # Risk exactly 1% of phantom equity
            risk_amount = self.phantom_equity * 0.01 
            sl_distance = abs(entry - sl)
            if sl_distance <= 0: sl_distance = 0.0001
            
            vol_scale = risk_amount / sl_distance # Scaling relative to edge
            
            if direction == 'BUY':
                floating = (current_price - entry) * vol_scale
            else:
                floating = (entry - current_price) * vol_scale
            
            equity_now += floating
            
            # Check Stop/Take Profit (Simulation)
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
        Score = (Equity * RegimeBoost * SessionBoost) / (1 + DrawdownPenalty)
        """
        base_score = self.phantom_equity
        
        # 1. Regime Boost (Predictive Switching)
        boost = 1.0
        if mtf_regime:
            hurst = mtf_regime.get('BASE', {}).get('hurst', 0.5)
            
            # Boost logic needs to check Class Name string AND Direction
            regime_trend = mtf_regime.get('trend', 'NEUTRAL') # Expecting 'BULLISH', 'BEARISH', 'RANGING'
            
            # GOLD OPTIMIZED: Favor trend strategies more aggressively
            # A. TREND STRATEGIES (TrendHawk, MACD_Cross, Sniper, LondonBreakout)
            is_trend_strat = any(x in self.name for x in ["TrendHawk", "MACD_Cross", "Sniper", "LondonBreakout"])
            if is_trend_strat:
                if hurst > 0.55: # Trending Regime - GOLD LOVES THIS
                    # Directional Matching with HIGHER boost for Gold
                    if 'BULLISH' in regime_trend:
                        if self.direction == 'LONG' or self.direction == 'BOTH': boost = 1.5
                        elif self.direction == 'SHORT': boost = 0.6
                    elif 'BEARISH' in regime_trend:
                        if self.direction == 'SHORT' or self.direction == 'BOTH': boost = 1.5
                        elif self.direction == 'LONG': boost = 0.6
                else: 
                     boost = 0.85

            # B. MEAN REVERSION STRATEGIES (MeanReverter, RSI_Matrix)
            elif any(x in self.name for x in ["MeanRev", "RSI_Matrix"]):
                if hurst < 0.45: # Mean Reversion Regime
                     boost = 1.2
                else:
                     boost = 0.7
                
        # 2. Drawdown Penalty (Stability)
        penalty = 1 + (self.max_drawdown * 2.0) 
        
        # 3. Hot Hand Bonus (Speed of Adaptation)
        streak_bonus = 1.0
        if self.win_streak >= 2: streak_bonus = 1.10
        if self.win_streak >= 3: streak_bonus = 1.25
        if self.win_streak >= 5: streak_bonus = 1.50
        
        # 4. SESSION-AWARE STRATEGY WEIGHTING (U4)
        # Gold has distinct session behaviors — weight strategies accordingly
        from datetime import datetime, timezone
        hour_utc = datetime.now(timezone.utc).hour
        session_boost = 1.0
        
        is_trend_strat = any(x in self.name for x in ["TrendHawk", "MACD_Cross", "Sniper", "LondonBreakout", "TrendPullback"])
        is_range_strat = any(x in self.name for x in ["MeanRev", "RSI_Matrix"])
        
        if 8 <= hour_utc < 16:  # London Session — Trend dominates
            if is_trend_strat: session_boost = 1.3
            elif is_range_strat: session_boost = 0.8
        elif 13 <= hour_utc < 17:  # NY Overlap — Max aggression for all
            session_boost = 1.2
        elif 0 <= hour_utc < 8:  # Asian Session — Range strategies shine
            if is_range_strat: session_boost = 1.3
            elif is_trend_strat: session_boost = 0.7
        elif 17 <= hour_utc < 24:  # Late NY — Low volume, reduce everything
            session_boost = 0.85
        
        final_score = (base_score * boost * streak_bonus * session_boost) / penalty
        return final_score

class TrendHawk(ShadowStrategy):
    """
    1. The 'Incumbent': Fractal Breakouts + Trend Following.
    Params: 'period', 'require_trend' (bool)
    """
    def _generate_raw_signal(self, df: pd.DataFrame, indicators: dict, mtf_data: dict) -> dict:
        current_price = df.iloc[-1]['close']
        candle_open = df.iloc[-1]['open']
        
        # Dynamic Period & Settings
        period = self.params.get('period', 20)
        require_trend = self.params.get('require_trend', False)
        
        ema_50 = indicators.get('ema_50', indicators.get('EMA_50', 0))
        
        prev_highs = df['high'].shift(1).rolling(period).max()
        prev_lows = df['low'].shift(1).rolling(period).min()
        
        high_x = prev_highs.iloc[-1]
        low_x = prev_lows.iloc[-1]
        
        if pd.isna(high_x) or pd.isna(low_x):
             return {'action': 'HOLD', 'confidence': 0, 'sl': 0, 'tp': 0, 'reason': "Insufficient Data for Period"}
        
        is_bullish_trend = True
        is_bearish_trend = True
        
        if require_trend:
             is_bullish_trend = current_price > ema_50
             is_bearish_trend = current_price < ema_50
        
        # BUY LOGIC (U6: Candle must be bullish — close > open)
        if (self.direction in ['LONG', 'BOTH']) and is_bullish_trend:
            if current_price >= high_x and current_price > candle_open:
                p_sl = low_x 
                risk = current_price - p_sl
                if risk <= 0: return {'action': 'HOLD', 'confidence': 0, 'sl': 0, 'tp': 0, 'reason': 'Zero Risk Distance'}
                return {'action': 'BUY', 'confidence': 0.85, 'sl': p_sl, 'tp': current_price + 2*risk, 'reason': f'Breakout above {period}p High'}
                
        # SELL LOGIC (U6: Candle must be bearish — close < open)
        if (self.direction in ['SHORT', 'BOTH']) and is_bearish_trend:
            if current_price <= low_x and current_price < candle_open:
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

from app.smc import SMCEngine

class Sniper(ShadowStrategy):
    """
    3. The 'Perfectionist': Only trades if multiple Timeframes align.
    """
    def _generate_raw_signal(self, df: pd.DataFrame, indicators: dict, mtf_data: dict) -> dict:
         current_price = df.iloc[-1]['close']
         
         # Initialize SMC Engine
         smc_engine = SMCEngine()
         smc_data = smc_engine.calculate_smc(df)
         order_blocks = smc_data.get('order_blocks', [])
         
         if not order_blocks:
             return {'action': 'HOLD', 'confidence': 0.0, 'sl': 0, 'tp': 0, 'reason': f"No Unmitigated Order Blocks Detected"}
             
         # BUG FIX B3: Check ALL unmitigated Order Blocks, not just index 0
         action = "HOLD"
         sl = 0
         tp = 0
         matched_ob = None
         
         for ob in order_blocks:
             ob_type = ob['type']
             ob_top = ob['price_top']
             ob_bottom = ob['price_bottom']
             
             if ob_type == "BULLISH_OB":
                 if current_price <= (ob_top * 1.001) and current_price >= ob_bottom:
                     action = "BUY"
                     sl = ob_bottom * 0.998
                     tp = current_price + 3*(current_price - sl)
                     matched_ob = ob
                     break
             elif ob_type == "BEARISH_OB":
                 if current_price >= (ob_bottom * 0.999) and current_price <= ob_top:
                     action = "SELL"
                     sl = ob_top * 1.002
                     tp = current_price - 3*(sl - current_price)
                     matched_ob = ob
                     break
                 
         if action == "HOLD":
             nearest_ob = order_blocks[0]
             return {'action': 'HOLD', 'confidence': 0.0, 'sl': 0, 'tp': 0, 'reason': f"No Sniper_Elite PA Setup ({current_price:.5f} vs H:{nearest_ob['price_top']:.5f}/L:{nearest_ob['price_bottom']:.5f})"}
                 
         # MATCH HTF Trend alignment — check HTF2 (H4) or HTF1 (H1)
         htf_aligned = True
         for tf_key in ['HTF2', 'HTF1']:
             if tf_key in mtf_data and hasattr(mtf_data[tf_key], 'empty') and not mtf_data[tf_key].empty:
                 htf_df = mtf_data[tf_key]
                 htf_close = htf_df.iloc[-1]['close']
                 htf_ema50 = htf_df['close'].ewm(span=50, adjust=False).mean().iloc[-1]
                 
                 if action == 'BUY' and htf_close < htf_ema50:
                     htf_aligned = False
                 if action == 'SELL' and htf_close > htf_ema50:
                     htf_aligned = False
                 break  # Use the first available HTF
         
         if not htf_aligned:
             return {'action': 'HOLD', 'confidence': 0.0, 'sl': 0, 'tp': 0, 'reason': f"HTF Alignment Fail - {action} blocked by HTF"}

         return {'action': action, 'confidence': 0.98, 'sl': sl, 'tp': tp, 'reason': f"SMC {matched_ob['type']} Mitigation"}

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
        
        # BUG FIX B1: Dynamic RSI Boundaries using Bollinger Bands logic
        # Previously checked for nonexistent 'rsi_history' column — dead code.
        # Now computes directly from df['RSI_14'] which MarketSensor always provides.
        if 'RSI_14' in df.columns and len(df) >= 20:
            recent_rsi = df['RSI_14'].tail(20).dropna()
            if len(recent_rsi) >= 10:
                rsi_mean = recent_rsi.mean()
                rsi_std = recent_rsi.std()
                if rsi_std > 0:
                    dynamic_upper = min(90, max(65, rsi_mean + (2.0 * rsi_std)))
                    dynamic_lower = max(10, min(35, rsi_mean - (2.0 * rsi_std)))
                else:
                    dynamic_upper = self.upper
                    dynamic_lower = self.lower
            else:
                dynamic_upper = self.upper
                dynamic_lower = self.lower
        else:
            dynamic_upper = self.upper
            dynamic_lower = self.lower
            
        # Regime Filter (Don't fade strong trends)
        hurst = 0.5
        try:
             hurst = mtf_data.get('analysis', {}).get('M15', {}).get('hurst', 0.5)
        except:
             pass
             
        if hurst > 0.6:
             return {'action': 'HOLD', 'confidence': 0, 'sl': 0, 'tp': 0, 'reason': f"Hurst {hurst:.2f} (Trending) - Unsafe for MeanRev"}
        
        # Logic: Buy Low, Sell High using Dynamic Volatility Bands
        if rsi < dynamic_lower:
            return {'action': 'BUY', 'confidence': 0.8, 'sl': df.iloc[-1]['close']*0.995, 'tp': df.iloc[-1]['close']*1.01, 'reason': f'Dynamic RSI Oversold ({rsi:.1f} < {dynamic_lower:.1f})'}
            
        if rsi > dynamic_upper:
             return {'action': 'SELL', 'confidence': 0.8, 'sl': df.iloc[-1]['close']*1.005, 'tp': df.iloc[-1]['close']*0.99, 'reason': f'Dynamic RSI Overbought ({rsi:.1f} > {dynamic_upper:.1f})'}
                
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
            macd_curr = df.iloc[-1].get('MACD_Fast', 0)
            signal_curr = df.iloc[-1].get('MACDs_Fast', 0)
            macd_prev = df.iloc[-2].get('MACD_Fast', 0)
            signal_prev = df.iloc[-2].get('MACDs_Fast', 0)
        else:
            macd_curr = df.iloc[-1].get('MACD', 0)
            signal_curr = df.iloc[-1].get('MACDs', 0)
            macd_prev = df.iloc[-2].get('MACD', 0)
            signal_prev = df.iloc[-2].get('MACDs', 0)
        
        current_price = df.iloc[-1]['close']
        
        # STRICT Crossover logic
        # MACD crosses ABOVE Signal
        if macd_curr > signal_curr and macd_prev <= signal_prev:
             speed_label = 'Fast' if self.speed == 'FAST' else 'Std'
             return {'action': 'BUY', 'confidence': 0.85, 'sl': current_price*0.995, 'tp': current_price*1.01, 'reason': f'MACD Cross Up ({speed_label})'}
             
        # MACD crosses BELOW Signal
        if macd_curr < signal_curr and macd_prev >= signal_prev:
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

class LiquiditySweeper(ShadowStrategy):
    """
    ULTIMATE GOLD STRATEGY 1: The Stop-Hunt Exploiter (Liquidity Sweeper)
    Logic: Detects when price spikes just past recent highs/lows (hunting retail stops)
    and immediately rejects back into the range. 
    """
    def _generate_raw_signal(self, df, indicators, mtf_data):
        if len(df) < 50: return {'action': 'HOLD', 'confidence': 0, 'sl': 0, 'tp': 0, 'reason': 'Not enough data'}
        
        current_candle = df.iloc[-1]
        prev_candle = df.iloc[-2]
        
        # Calculate recent Lookback High/Low (e.g. last 40 candles = roughly Asian session range on M5)
        # Exclude the current and previous candle from the lookback to find the *established* range
        lookback_df = df.iloc[-42:-2]
        recent_high = lookback_df['high'].max()
        recent_low = lookback_df['low'].min()
        
        atr = indicators.get('atr', indicators.get('ATR_14', 2.0))
        
        # 1. BEARISH SWEEP (Short Opportunity)
        # Prev candle spiked ABOVE the high (triggering buy stops), but closed weakly (rejection).
        # We now mathematically measure the sweep wick.
        upper_wick = prev_candle['high'] - max(prev_candle['open'], prev_candle['close'])
        
        is_bearish_sweep = (
            prev_candle['high'] > recent_high and        # Pierced the recent high
            upper_wick > (atr * 0.4) and                 # Serious liquidity trap (Wick size is structurally huge)
            prev_candle['close'] < (recent_high + atr*0.1) and # Rejected to close near/below the high
            current_candle['close'] < prev_candle['low']       # Current candle confirms downside
        )
        
        if is_bearish_sweep and self.direction in ['BOTH', 'SHORT']:
            sl = prev_candle['high'] + (atr * 0.2) # Tight SL just above the sweep wick
            tp = current_candle['close'] - (abs(sl - current_candle['close']) * 3.0) # 1:3 R:R
            return {'action': 'SELL', 'confidence': 0.95, 'sl': sl, 'tp': tp, 'reason': "Liquidity Sweep (Stop Hunt High - Massive Wick)"}
            
        # 2. BULLISH SWEEP (Long Opportunity)
        lower_wick = min(prev_candle['open'], prev_candle['close']) - prev_candle['low']
        
        is_bullish_sweep = (
            prev_candle['low'] < recent_low and         # Pierced the recent low
            lower_wick > (atr * 0.4) and                # Serious liquidity trap
            prev_candle['close'] > (recent_low - atr*0.1) and # Rejected to close near/above the low
            current_candle['close'] > prev_candle['high']     # Current candle confirms upside
        )
        
        if is_bullish_sweep and self.direction in ['BOTH', 'LONG']:
            sl = prev_candle['low'] - (atr * 0.2) # Tight SL below the sweep wick
            tp = current_candle['close'] + (abs(current_candle['close'] - sl) * 3.0) # 1:3 R:R
            return {'action': 'BUY', 'confidence': 0.95, 'sl': sl, 'tp': tp, 'reason': "Liquidity Sweep (Stop Hunt Low - Massive Wick)"}
            
        return {'action': 'HOLD', 'confidence': 0, 'sl': 0, 'tp': 0, 'reason': 'No Valid Sweep Pattern'}

    def clone(self, new_params: dict = None) -> 'LiquiditySweeper':
        return LiquiditySweeper(self.name, self.direction)

class NewsArbitrage(ShadowStrategy):
    """
    ULTIMATE GOLD STRATEGY 2: News Arbitrage (Volatility Breakout)
    Logic: Designed to catch explosive volatility following major US/EUR data releases.
    If the bot is currently in a high-volatility window triggered by a recent news event,
    it identifies the tight pre-news range and fires a breakout trade.
    """
    def _generate_raw_signal(self, df, indicators, mtf_data):
        if len(df) < 15: return {'action': 'HOLD', 'confidence': 0, 'sl': 0, 'tp': 0, 'reason': 'Not enough data'}
        
        current_candle = df.iloc[-1]
        
        # Check if we are in a Volatility Expansion phase initiated by news
        # (This strategy requires the main.py NewsHarvester to flag recent high-impact news)
        # We simulate that trigger by requiring extreme volume + ATR expansion + Squeeze Breakout
        
        is_expanding = not indicators.get('squeeze_on', True) # Squeeze OFF means Expanding
        atr = indicators.get('atr', indicators.get('ATR_14', 2.0))
        
        # Calculate recent consolidation range (last 10 candles before expansion)
        recent_range_df = df.iloc[-12:-2]
        range_high = recent_range_df['high'].max()
        range_low = recent_range_df['low'].min()
        range_size = range_high - range_low
        
        # Condition: Very tight consolidation prior to the current candle
        is_tight_range = range_size < (atr * 1.5) 
        
        # 1. BULLISH BREAKOUT
        # Price instantly rips above the tight range into expansion
        if is_expanding and is_tight_range and current_candle['close'] > range_high:
            if self.direction in ['BOTH', 'LONG']:
                sl = range_low - (atr * 0.2) # Tight SL below the consolidation
                tp = current_candle['close'] + (atr * 4.0) # Massive R:R for news spikes
                return {'action': 'BUY', 'confidence': 0.90, 'sl': sl, 'tp': tp, 'reason': "News Volatility Breakout (Up)"}
                
        # 2. BEARISH BREAKOUT
        # Price instantly rips below the tight range into expansion
        if is_expanding and is_tight_range and current_candle['close'] < range_low:
            if self.direction in ['BOTH', 'SHORT']:
                sl = range_high + (atr * 0.2)
                tp = current_candle['close'] - (atr * 4.0)
                return {'action': 'SELL', 'confidence': 0.90, 'sl': sl, 'tp': tp, 'reason': "News Volatility Breakout (Down)"}
                
        return {'action': 'HOLD', 'confidence': 0, 'sl': 0, 'tp': 0, 'reason': 'No Breakout Criteria'}

    def clone(self, new_params: dict = None) -> 'NewsArbitrage':
        return NewsArbitrage(self.name, self.direction)

class StatArb_DXY(ShadowStrategy):
    """
    ULTIMATE GOLD STRATEGY 3: Statistical Arbitrage & Intermarket Cointegration
    Logic: Triggers when Gold and the US Dollar Index (DXY) are structurally mispriced.
    Gold and DXY should be inversely correlated. If they move in the same direction,
    this strategy plays the fundamental mean reversion.
    """
    def _generate_raw_signal(self, df, indicators, mtf_data):
        macro = mtf_data.get('macro', {})
        if not macro.get('dxy_active', False):
            return {'action': 'HOLD', 'confidence': 0, 'sl': 0, 'tp': 0, 'reason': 'DXY Data Unavailable'}
            
        div_score = macro.get('divergence_score', 0.0)
        current_price = df.iloc[-1]['close']
        atr = indicators.get('atr', indicators.get('ATR_14', 2.0))
        
        # BUY LOGIC: Gold is anomalously weak (-2.0 Z-Score)
        if div_score <= -2.0 and self.direction in ['BOTH', 'LONG']:
            sl = current_price - (atr * 1.5)
            tp = current_price + (atr * 3.0)
            return {'action': 'BUY', 'confidence': min(abs(div_score) * 0.3, 0.9), 'sl': sl, 'tp': tp, 'reason': f"StatArb DXY Z-Score ({div_score:.2f})"}
            
        # SELL LOGIC: Gold is anomalously strong (+2.0 Z-Score)
        if div_score >= 2.0 and self.direction in ['BOTH', 'SHORT']:
            
            # --- THE THIRD VARIABLE RISK (PANIC GUARD) ---
            # Do not short a breakout if the entire market is panicking (Safe Haven Convergence).
            if macro.get('vix_spike', False):
                return {'action': 'HOLD', 'confidence': 0, 'sl': 0, 'tp': 0, 'reason': 'VETO: Safe Haven Convergence (VIX Proxy Spike)'}
                
            sl = current_price + (atr * 1.5)
            tp = current_price - (atr * 3.0)
            return {'action': 'SELL', 'confidence': min(div_score * 0.3, 0.9), 'sl': sl, 'tp': tp, 'reason': f"StatArb DXY Z-Score ({div_score:.2f})"}
            
        return {'action': 'HOLD', 'confidence': 0, 'sl': 0, 'tp': 0, 'reason': 'Macro Cointegration Stable'}

    def clone(self, new_params: dict = None) -> 'StatArb_DXY':
        return StatArb_DXY(self.name, self.direction)

class LondonBreakout(ShadowStrategy):
    """
    U2: London Session Breakout Strategy.
    Gold's #1 institutional intraday pattern: price establishes a range during the
    Asian session (00:00–08:00 UTC), then breaks out at the London open.
    Fires once per day between 08:00-10:00 UTC.
    """
    def _generate_raw_signal(self, df: pd.DataFrame, indicators: dict, mtf_data: dict) -> dict:
        from datetime import timezone
        
        current_price = df.iloc[-1]['close']
        current_time = df.iloc[-1]['time']
        
        # Handle timezone-aware or naive datetimes
        if hasattr(current_time, 'hour'):
            hour_utc = current_time.hour
        else:
            hour_utc = pd.Timestamp(current_time).hour
        
        # Only active during London open window (08:00-10:00 UTC)
        if hour_utc < 8 or hour_utc >= 10:
            return {'action': 'HOLD', 'confidence': 0, 'sl': 0, 'tp': 0, 'reason': 'Outside London Breakout Window'}
        
        # Calculate Asian Session Range (00:00-08:00 UTC candles)
        # Filter candles from today's Asian session
        asian_candles = df[df['time'].apply(lambda t: t.hour if hasattr(t, 'hour') else pd.Timestamp(t).hour) < 8]
        asian_today = asian_candles.tail(32)  # ~8 hours of M15 candles
        
        if len(asian_today) < 8:
            return {'action': 'HOLD', 'confidence': 0, 'sl': 0, 'tp': 0, 'reason': 'Insufficient Asian Session Data'}
        
        asian_high = asian_today['high'].max()
        asian_low = asian_today['low'].min()
        asian_range = asian_high - asian_low
        
        # Skip if range is too tight (squeeze) or too wide (already moved)
        atr = indicators.get('atr', indicators.get('ATR_14', 2.0))
        if asian_range < atr * 0.3:
            return {'action': 'HOLD', 'confidence': 0, 'sl': 0, 'tp': 0, 'reason': f'Asian Range Too Tight ({asian_range:.2f})'}
        if asian_range > atr * 3.0:
            return {'action': 'HOLD', 'confidence': 0, 'sl': 0, 'tp': 0, 'reason': f'Asian Range Too Wide ({asian_range:.2f})'}
        
        candle_open = df.iloc[-1]['open']
        
        # Bullish Breakout: Close above Asian High with bullish candle
        if current_price > asian_high and current_price > candle_open:
            sl = asian_low
            tp = current_price + (asian_range * 2.0)  # 2× the Asian range
            return {'action': 'BUY', 'confidence': 0.90, 'sl': sl, 'tp': tp, 'reason': f'London Breakout BUY (Range: {asian_range:.2f})'}
        
        # Bearish Breakout: Close below Asian Low with bearish candle
        if current_price < asian_low and current_price < candle_open:
            sl = asian_high
            tp = current_price - (asian_range * 2.0)
            return {'action': 'SELL', 'confidence': 0.90, 'sl': sl, 'tp': tp, 'reason': f'London Breakout SELL (Range: {asian_range:.2f})'}
        
        return {'action': 'HOLD', 'confidence': 0, 'sl': 0, 'tp': 0, 'reason': f'No London Breakout ({current_price:.2f} inside {asian_low:.2f}-{asian_high:.2f})'}
    
    def clone(self, new_params: dict = None) -> 'LondonBreakout':
        return LondonBreakout(self.name, self.direction)

class FVGRetracement(ShadowStrategy):
    """
    U3: Fair Value Gap Retracement Strategy.
    Trades the gap fill when price returns to an unmitigated FVG zone.
    FVGs form 5-10× more frequently than Order Blocks, providing significantly
    more high-probability SMC entry points.
    """
    def _generate_raw_signal(self, df: pd.DataFrame, indicators: dict, mtf_data: dict) -> dict:
        current_price = df.iloc[-1]['close']
        candle_open = df.iloc[-1]['open']
        
        smc_engine = SMCEngine()
        fvgs = smc_engine.detect_fvgs(df)
        
        if not fvgs:
            return {'action': 'HOLD', 'confidence': 0, 'sl': 0, 'tp': 0, 'reason': 'No FVGs Detected'}
        
        atr = indicators.get('atr', indicators.get('ATR_14', 2.0))
        
        # Check recent FVGs (last 5) for price re-entry
        for fvg in reversed(fvgs[-5:]):
            fvg_top = fvg['top']
            fvg_bottom = fvg['bottom']
            fvg_mid = (fvg_top + fvg_bottom) / 2
            fvg_size = fvg_top - fvg_bottom
            
            # Skip insignificant FVGs (smaller than 0.2 ATR)
            if fvg_size < atr * 0.2:
                continue
            
            if fvg['type'] == 'BULLISH_FVG':
                # Price has dropped back into the Bullish FVG — BUY the fill
                if fvg_bottom <= current_price <= fvg_top and current_price > candle_open:
                    sl = fvg_bottom - (atr * 0.5)
                    risk = current_price - sl
                    tp = current_price + (risk * 2.0)  # 1:2 R:R
                    return {'action': 'BUY', 'confidence': 0.82, 'sl': sl, 'tp': tp, 'reason': f'FVG Retracement BUY ({fvg_bottom:.2f}-{fvg_top:.2f})'}
            
            elif fvg['type'] == 'BEARISH_FVG':
                # Price has pushed back up into the Bearish FVG — SELL the fill
                if fvg_bottom <= current_price <= fvg_top and current_price < candle_open:
                    sl = fvg_top + (atr * 0.5)
                    risk = sl - current_price
                    tp = current_price - (risk * 2.0)
                    return {'action': 'SELL', 'confidence': 0.82, 'sl': sl, 'tp': tp, 'reason': f'FVG Retracement SELL ({fvg_bottom:.2f}-{fvg_top:.2f})'}
        
        return {'action': 'HOLD', 'confidence': 0, 'sl': 0, 'tp': 0, 'reason': 'Price Not in Any FVG Zone'}
    
    def clone(self, new_params: dict = None) -> 'FVGRetracement':
        return FVGRetracement(self.name, self.direction)

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
        
        # 7. ULTIMATE GOLD STRATEGY: Liquidity Sweeper
        self.strategies.append(LiquiditySweeper("LiquiditySweeper_LONG", direction="LONG"))
        self.strategies.append(LiquiditySweeper("LiquiditySweeper_SHORT", direction="SHORT"))
        self.strategies.append(LiquiditySweeper("LiquiditySweeper_BOTH", direction="BOTH"))

        # 8. ULTIMATE GOLD STRATEGY: News Arbitrage (Breakout Sniper)
        self.strategies.append(NewsArbitrage("NewsArbitrage_LONG", direction="LONG"))
        self.strategies.append(NewsArbitrage("NewsArbitrage_SHORT", direction="SHORT"))
        self.strategies.append(NewsArbitrage("NewsArbitrage_BOTH", direction="BOTH"))
        
        # 9. ULTIMATE GOLD STRATEGY: Statistical Arbitrage (Macro Cointegration)
        self.strategies.append(StatArb_DXY("StatArb_DXY_LONG", direction="LONG"))
        self.strategies.append(StatArb_DXY("StatArb_DXY_SHORT", direction="SHORT"))
        self.strategies.append(StatArb_DXY("StatArb_DXY_BOTH", direction="BOTH"))
        
        # 10. BEAST MODE: London Breakout (U2) — Gold's #1 institutional pattern
        self.strategies.append(LondonBreakout("LondonBreakout_LONG", direction="LONG"))
        self.strategies.append(LondonBreakout("LondonBreakout_SHORT", direction="SHORT"))
        self.strategies.append(LondonBreakout("LondonBreakout_BOTH", direction="BOTH"))
        
        # 11. BEAST MODE: FVG Retracement (U3) — Trade gap fills for high-frequency SMC entries
        self.strategies.append(FVGRetracement("FVGRetracement_LONG", direction="LONG"))
        self.strategies.append(FVGRetracement("FVGRetracement_SHORT", direction="SHORT"))
        self.strategies.append(FVGRetracement("FVGRetracement_BOTH", direction="BOTH"))
        
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
            'TrendPullback': TrendPullback,
            'LiquiditySweeper': LiquiditySweeper,
            'NewsArbitrage': NewsArbitrage,
            'StatArb_DXY': StatArb_DXY,
            'LondonBreakout': LondonBreakout,
            'FVGRetracement': FVGRetracement
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
                    
                    # EXTINCTION CHECK ON LOAD:
                    # If loaded state is damaged (missing key species), repair it immediately.
                    required_seeds = [
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
                        (LiquiditySweeper, "LiquiditySweeper_BOTH", "BOTH", {}),
                        (NewsArbitrage, "NewsArbitrage_BOTH",    "BOTH", {}),
                        (StatArb_DXY,   "StatArb_DXY_BOTH",      "BOTH",  {}),
                        (LondonBreakout, "LondonBreakout_BOTH",  "BOTH",  {}),
                        (FVGRetracement, "FVGRetracement_BOTH",  "BOTH",  {}),
                    ]
                    
                    injected = 0
                    for cls, name, direction, params in required_seeds:
                        has_species = any(isinstance(s, cls) and s.direction == direction for s in self.strategies)
                        if not has_species:
                            seed = cls(name, direction=direction, params=params)
                            # Replace weakest if full
                            if len(self.strategies) >= 100:
                                self.strategies.sort(key=lambda s: s.get_quality_score()) # Sort ascending (weakest first)
                                self.strategies[0] = seed # Replace weakest
                            else:
                                self.strategies.append(seed)
                            injected += 1
                            print(f"🛡️ REPAIR ON LOAD: Injected {name} (species was missing on disk!)")
                            
                    if injected > 0:
                        print(f"🛡️ Repaired ecosystem. Injected {injected} missing species.")
                    
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
            
            # FIX: Always generate and cache signal to make it available for Jury consensus polling
            signal = strat.generate_signal(df, indicators, mtf_data)
            self._cached_signals[strat.name] = signal  # Cache for reuse
            
            if not strat.active_trade:
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
                        "Sniper_Elite": ["Sniper_Elite"],
                        "LiquiditySweeper_LONG": ["LiquiditySweeper", "LONG"],
                        "LiquiditySweeper_SHORT": ["LiquiditySweeper", "SHORT"],
                        "NewsArbitrage_LONG": ["NewsArbitrage", "LONG"],
                        "NewsArbitrage_SHORT": ["NewsArbitrage", "SHORT"],
                        "StatArb_DXY_LONG": ["StatArb_DXY", "LONG"],
                        "StatArb_DXY_SHORT": ["StatArb_DXY", "SHORT"],
                        "LondonBreakout_LONG": ["LondonBreakout", "LONG"],
                        "LondonBreakout_SHORT": ["LondonBreakout", "SHORT"],
                        "FVGRetracement_LONG": ["FVGRetracement", "LONG"],
                        "FVGRetracement_SHORT": ["FVGRetracement", "SHORT"]
                    }
                    search_terms = tag_map.get(allow_tag, [allow_tag])
                    if all(term in strat.name for term in search_terms):
                        is_match = True
                        break
                        
                    # ALSO ALLOW 'BOTH' direction if LONG/SHORT was requested
                    if allow_tag.endswith("_LONG") or allow_tag.endswith("_SHORT"):
                        both_terms = [t.replace("LONG", "BOTH").replace("SHORT", "BOTH") for t in search_terms]
                        if all(term in strat.name for term in both_terms):
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
            (LiquiditySweeper, "LiquiditySweeper_BOTH", "BOTH", {}),
            (NewsArbitrage, "NewsArbitrage_BOTH",    "BOTH", {}),
            (StatArb_DXY,   "StatArb_DXY_BOTH",      "BOTH",  {}),
            (LondonBreakout, "LondonBreakout_BOTH",  "BOTH",  {}),
            (FVGRetracement, "FVGRetracement_BOTH",  "BOTH",  {}),
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

    def get_consensus_signal(self, df, indicators, mtf_data, top_n=9) -> dict:
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
                        "Sniper_Elite": ["Sniper_Elite"],
                        "LiquiditySweeper_LONG": ["LiquiditySweeper", "LONG"],
                        "LiquiditySweeper_SHORT": ["LiquiditySweeper", "SHORT"],
                        "NewsArbitrage_LONG": ["NewsArbitrage", "LONG"],
                        "NewsArbitrage_SHORT": ["NewsArbitrage", "SHORT"],
                        "StatArb_DXY_LONG": ["StatArb_DXY", "LONG"],
                        "StatArb_DXY_SHORT": ["StatArb_DXY", "SHORT"]
                    }
                    search_terms = tag_map.get(allow_tag, [allow_tag])
                    if all(term in strat.name for term in search_terms):
                        is_match = True
                        break
                        
                    # ALSO ALLOW 'BOTH' direction if LONG/SHORT was requested
                    if allow_tag.endswith("_LONG") or allow_tag.endswith("_SHORT"):
                        both_terms = [t.replace("LONG", "BOTH").replace("SHORT", "BOTH") for t in search_terms]
                        if all(term in strat.name for term in both_terms):
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
        strategy_types = ["TrendHawk", "MeanRev", "RSI_Matrix", "MACD_Cross", "Sniper", "TrendPullback", "LiquiditySweeper", "NewsArbitrage", "StatArb"]
        
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
             rookies = [s for s in candidates if len(s.trade_history) == 0 and s.name not in [j.name for j in jury]]
             if rookies:
                 rookie = random.choice(rookies)
                 # Remove lowest scoring member of current jury
                 if jury:
                     # Sort jury by score temporarily to find weakest link
                     jury.sort(key=lambda s: self.last_scores.get(s.name, 0))
                     removed = jury.pop(0) # Remove weakest
                     jury.append(rookie)
                     print(f"🕵️ SCOUT PROTOCOL: Swapped {removed.name} for Rookie {rookie.name}")
        
        # U1: WEIGHTED JURY VOTING — each vote weighted by quality_score
        vote_weights = {'BUY': 0.0, 'SELL': 0.0, 'HOLD': 0.0}
        vote_counts = {'BUY': 0, 'SELL': 0, 'HOLD': 0}
        reasons = []
        voter_signals = {'BUY': [], 'SELL': []}
        
        print(f"⚖️ THE JURY IS IN SESSION. Members: {[s.name for s in jury]}")
        
        for juror in jury:
            sig = getattr(self, '_cached_signals', {}).get(juror.name) or juror.generate_signal(df, indicators, mtf_data)
            action = sig['action']
            
            # Weight = quality score of this juror (proven performers count more)
            weight = self.last_scores.get(juror.name, 10000.0)
            vote_weights[action] = vote_weights.get(action, 0) + weight
            vote_counts[action] = vote_counts.get(action, 0) + 1
            
            reason_stub = sig.get('reason', 'No Signal')
            reasons.append(f"{juror.name}: {action} [{reason_stub}]")
            
            if action in ['BUY', 'SELL'] and sig.get('sl', 0) != 0:
                voter_signals[action].append({
                    'name': juror.name,
                    'sl': sig['sl'],
                    'tp': sig['tp'],
                    'confidence': sig.get('confidence', 0.5)
                })
            
        # Decision Logic (Weighted)
        final_action = "HOLD"
        confidence = 0.0
        details = " | ".join(reasons)
        
        buy_votes = vote_counts['BUY']
        sell_votes = vote_counts['SELL']
        buy_weight = vote_weights['BUY']
        sell_weight = vote_weights['SELL']
        hold_weight = vote_weights['HOLD']
        total_weight = buy_weight + sell_weight + hold_weight
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
            
        # 2. WEIGHTED MAJORITY: Side with more weight wins (must have 2+ votes)
        elif buy_votes >= 2 and buy_weight > sell_weight and buy_weight > hold_weight:
            final_action = "BUY"
            confidence = 0.6 + (buy_weight / total_weight * 0.35) if total_weight > 0 else 0.6
            details = f"WEIGHTED BUY {buy_votes}v{sell_votes} (W:{buy_weight:.0f} vs {sell_weight:.0f}) ({details})"
        elif sell_votes >= 2 and sell_weight > buy_weight and sell_weight > hold_weight:
            final_action = "SELL"
            confidence = 0.6 + (sell_weight / total_weight * 0.35) if total_weight > 0 else 0.6
            details = f"WEIGHTED SELL {sell_votes}v{buy_votes} (W:{sell_weight:.0f} vs {buy_weight:.0f}) ({details})"
            
        # 3. STRONG MINORITY: Even 1 high-scoring voter can win if their weight
        #    exceeds combined opposing weight (elite strategist override)
        elif buy_votes >= 1 and sell_votes == 0 and buy_weight > hold_weight * 0.4:
            final_action = "BUY"
            confidence = 0.55 + (buy_weight / total_weight * 0.2) if total_weight > 0 else 0.55
            details = f"WEIGHTED LONE WOLF BUY (W:{buy_weight:.0f} vs HOLD:{hold_weight:.0f}) ({details})"
        elif sell_votes >= 1 and buy_votes == 0 and sell_weight > hold_weight * 0.4:
            final_action = "SELL"
            confidence = 0.55 + (sell_weight / total_weight * 0.2) if total_weight > 0 else 0.55
            details = f"WEIGHTED LONE WOLF SELL (W:{sell_weight:.0f} vs HOLD:{hold_weight:.0f}) ({details})"
            
        # 4. CONFLICT (both sides have votes) — weight decides
        elif buy_votes >= 1 and sell_votes >= 1:
            if buy_weight > sell_weight * 1.3:  # Need 30% weight margin
                final_action = "BUY"
                confidence = 0.55
                details = f"CONFLICT RESOLVED BUY (W:{buy_weight:.0f} vs {sell_weight:.0f}) | {details}"
            elif sell_weight > buy_weight * 1.3:
                final_action = "SELL"
                confidence = 0.55
                details = f"CONFLICT RESOLVED SELL (W:{sell_weight:.0f} vs {buy_weight:.0f}) | {details}"
            else:
                final_action = "HOLD"
                details = f"DEADLOCK (BUY_W:{buy_weight:.0f} vs SELL_W:{sell_weight:.0f}) | {details}"

        else:
             final_action = "HOLD"
             details = f"HUNG JURY ({details})"
             
        # =========================================================
        # INSTITUTIONAL MACRO VETO (The DXY Defense)
        # =========================================================
        # If DXY (US Dollar Index) is strongly trending, it overrides technicals.
        macro = mtf_data.get('macro', {})
        dxy_active = macro.get('dxy_active', False)
        div_score = macro.get('divergence_score', 0.0)
        
        if final_action != "HOLD" and dxy_active:
             # If divergence_score > +0.6, Dollar is violently pumping. Gold should drop.
             # Veto BUYS.
             if final_action == "BUY" and div_score > 0.6:
                 final_action = "HOLD"
                 confidence = 0.0
                 details = f"VETOED (MACRO): BUY blocked. DXY is Pumping violently (Score +{div_score:.2f}) | {details}"
             
             # If divergence_score < -0.6, Dollar is collapsing. Gold should rally.
             # Veto SELLS.
             elif final_action == "SELL" and div_score < -0.6:
                 final_action = "HOLD"
                 confidence = 0.0
                 details = f"VETOED (MACRO): SELL blocked. DXY is Collapsing (Score {div_score:.2f}) | {details}"
                 
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
            'jury_votes': vote_counts,
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
