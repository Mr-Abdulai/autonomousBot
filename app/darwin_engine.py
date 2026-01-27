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
    def __init__(self, name: str):
        self.name = name
        self.phantom_equity = 10000.0 # Virtual $10k start
        self.active_trade = None # Dict: {'entry': float, 'type': 'BUY'/'SELL'}
        self.trade_history = [] # List of closed trades
        self.win_streak = 0
        self.loss_streak = 0
        
    @abstractmethod
    def generate_signal(self, df: pd.DataFrame, indicators: dict, mtf_data: dict) -> dict:
        """
        Returns: {'action': 'BUY'/'SELL'/'HOLD', 'confidence': float, 'sl': float, 'tp': float}
        """
        pass
        
    def update_performance(self, current_price: float):
        """Updates Phantom Equity based on active virtual trades."""
        if not self.active_trade:
            return
            
        # Check simulated SL/TP HIT
        entry = self.active_trade['entry']
        sl = self.active_trade['sl']
        tp = self.active_trade['tp']
        direction = self.active_trade['type']
        
        pnl = 0.0
        closed = False
        
        if direction == 'BUY':
            if current_price <= sl:
                pnl = (sl - entry) # Loss
                closed = True
            elif current_price >= tp:
                pnl = (tp - entry) # Profit
                closed = True
        elif direction == 'SELL':
            if current_price >= sl:
                pnl = (entry - sl) # Loss
                closed = True
            elif current_price <= tp:
                pnl = (entry - tp) # Profit
                closed = True
                
        if closed:
            # Simple unit sizing (1 unit) for standardized comparison
            self.phantom_equity += pnl * 1000 # Scaling factor
            self.trade_history.append({'pnl': pnl, 'time': datetime.now()})
            if pnl > 0:
                self.win_streak += 1
                self.loss_streak = 0
            else:
                self.loss_streak += 1
                self.win_streak = 0
            self.active_trade = None

class TrendHawk(ShadowStrategy):
    """
    1. The 'Incumbent': Fractal Breakouts + Trend Following.
    Uses Phase 81 Logic (Fractals).
    """
    def generate_signal(self, df: pd.DataFrame, indicators: dict, mtf_data: dict) -> dict:
        # Use Fractal Levels from indicators if available, else standard
        current_price = df.iloc[-1]['close']
        
        # Simple Fractal Breakout Logic for Shadow Mode
        # (We assume 'fractal_high' columns exist or we approximate)
        # Note: For speed, we might use Donchian Channels as proxy for Fractals in shadow mode
        
        # Proxy Logic: Break of 20-period High/Low
        high_20 = df['high'].rolling(20).max().iloc[-1]
        low_20 = df['low'].rolling(20).min().iloc[-1]
        ema_50 = indicators.get('EMA_50', 0)
        
        # Trend Filter
        if current_price > ema_50:
            # Bullish Breakout
            if current_price >= high_20:
                p_sl = low_20 # Stop at low
                risk = current_price - p_sl
                if risk <= 0: return {'action': 'HOLD', 'confidence': 0, 'sl': 0, 'tp': 0}
                return {'action': 'BUY', 'confidence': 0.85, 'sl': p_sl, 'tp': current_price + 2*risk}
                
        elif current_price < ema_50:
            # Bearish Breakout
            if current_price <= low_20:
                p_sl = high_20 # Stop at high
                risk = p_sl - current_price
                if risk <= 0: return {'action': 'HOLD', 'confidence': 0, 'sl': 0, 'tp': 0}
                return {'action': 'SELL', 'confidence': 0.85, 'sl': p_sl, 'tp': current_price - 2*risk}
                
        return {'action': 'HOLD', 'confidence': 0.0, 'sl': 0, 'tp': 0}

class MeanReverter(ShadowStrategy):
    """
    2. The 'Contrarian': Fading Bollinger Band Extremes.
    Best for: Ranges / Chop.
    """
    def generate_signal(self, df: pd.DataFrame, indicators: dict, mtf_data: dict) -> dict:
        latest = df.iloc[-1]
        close = latest['close']
        bb_upper = indicators.get('BB_Upper', 0)
        bb_lower = indicators.get('BB_Lower', 0)
        rsi = indicators.get('RSI_14', 50)
        ema_50 = indicators.get('EMA_50', close)
        
        if bb_upper == 0: return {'action': 'HOLD', 'confidence': 0, 'sl': 0, 'tp': 0}
        
        # Fade Highs (Sell at Top of Range)
        if close > bb_upper and rsi > 70:
            return {'action': 'SELL', 'confidence': 0.75, 'sl': close * 1.002, 'tp': ema_50}
            
        # Fade Lows (Buy at Bottom of Range)
        if close < bb_lower and rsi < 30:
            return {'action': 'BUY', 'confidence': 0.75, 'sl': close * 0.998, 'tp': ema_50}
            
        return {'action': 'HOLD', 'confidence': 0.0, 'sl': 0, 'tp': 0}

class Sniper(ShadowStrategy):
    """
    3. The 'Perfectionist': Only trades if multiple Timeframes align.
    """
    def generate_signal(self, df: pd.DataFrame, indicators: dict, mtf_data: dict) -> dict:
         # Check Alignment first
         # We need access to MTF analysis.
         # For shadow mode, we can check basic EMAs of H1
         
         if 'H1' not in mtf_data or mtf_data['H1'].empty:
             return {'action': 'HOLD', 'confidence': 0, 'sl': 0, 'tp': 0}
             
         h1_df = mtf_data['H1']
         h1_close = h1_df.iloc[-1]['close']
         h1_ma = h1_df['close'].rolling(50).mean().iloc[-1]
         
         # Base Logic from TrendHawk
         base_signal = TrendHawk("temp").generate_signal(df, indicators, mtf_data)
         
         if base_signal['action'] == 'BUY':
             # Confirm with H1 Trend
             if h1_close > h1_ma:
                 base_signal['confidence'] = 0.95 # BOOST
                 return base_signal
                 
         elif base_signal['action'] == 'SELL':
             if h1_close < h1_ma:
                 base_signal['confidence'] = 0.95 # BOOST
                 return base_signal
                 
         return {'action': 'HOLD', 'confidence': 0.0, 'sl': 0, 'tp': 0}

class DarwinEngine:
    def __init__(self):
        self.strategies = [
            TrendHawk("TrendHawk"),
            MeanReverter("MeanReverter"),
            Sniper("Sniper")
        ]
        self.leader = self.strategies[0]
        
    def update(self, df: pd.DataFrame, indicators: dict, mtf_data: dict):
        current_price = df.iloc[-1]['close']
        
        for strat in self.strategies:
            # 1. Update Performance (Check if shadow trades closed)
            strat.update_performance(current_price)
            
            # 2. Generate New Shadow Trades (if flat)
            if not strat.active_trade:
                signal = strat.generate_signal(df, indicators, mtf_data)
                if signal['action'] != 'HOLD':
                    strat.active_trade = {
                        'entry': current_price,
                        'type': signal['action'],
                        'sl': signal['sl'],
                        'tp': signal['tp']
                    }
                    
        # 3. Determine Leader (Simple Equity Check)
        # Advanced: Use Sharpe Ratio or recent slope
        self.strategies.sort(key=lambda s: s.phantom_equity, reverse=True)
        self.leader = self.strategies[0]
        
    def get_alpha_signal(self, df, indicators, mtf_data) -> dict:
        """Returns the signal from the WINNING strategy."""
        best_strat_name = self.leader.name
        # The 'Leader' might have an active trade OR want to enter now.
        # But 'main.py' uses this to enter LIVE trades.
        # So we ask the leader for its signal NOW.
        
        signal = self.leader.generate_signal(df, indicators, mtf_data)
        
        # Add metadata
        signal['source'] = f"DarwinLeader::{best_strat_name}"
        signal['darwin_score'] = self.leader.phantom_equity
        
        return signal

    def get_leaderboard(self) -> str:
        s = "Darwin Leaderboard:\n"
        for strat in self.strategies:
            s += f" - {strat.name}: ${strat.phantom_equity:.2f} (Streak: {strat.win_streak}W)\n"
        return s
