import pandas as pd
import MetaTrader5 as mt5
import numpy as np

class MacroSensor:
    """
    Institutional Upgrade 1: Statistical Arbitrage & Intermarket Cointegration.
    Tracks XAUUSD's correlation against the US Dollar Index (DXY) and US 10-Year Treasury Yields (US10Y).
    """
    def __init__(self):
        self.dxy_symbol = None
        self.us10y_symbol = None
        self.is_initialized = False

    def initialize(self):
        if not mt5.initialize():
            print("MacroSensor: MT5 init failed.")
            return False
        
        # Discover Symbols
        self.dxy_symbol = self._find_symbol(["DXY", "USDX", "DOLLAR"])
        self.us10y_symbol = self._find_symbol(["US10Y", "US10YR", "TNX"])
        
        if self.dxy_symbol:
            print(f"🌍 MacroSensor Connected to Dollar Index: {self.dxy_symbol}")
        else:
            print("⚠️ MacroSensor: Dollar Index (DXY) not available on this broker.")
            
        self.is_initialized = True
        return True

    def _find_symbol(self, aliases):
        all_symbols = mt5.symbols_get()
        if not all_symbols: return None
        
        symbol_names = [s.name for s in all_symbols]
        
        for alias in aliases:
            # Exact Match
            if alias in symbol_names:
                return alias
            
            # Partial / Suffix Match
            for name in symbol_names:
                if alias in name.upper():
                    return name
                    
        return None

    def get_macro_divergence(self, gold_df: pd.DataFrame) -> dict:
        """
        Calculates real-time correlation and detects StatArb divergences.
        Requires the current Gold M15 or M5 dataframe.
        """
        if not self.is_initialized:
            self.initialize()
            
        result = {
            'dxy_correlation': 0.0,
            'divergence_score': 0.0, # Positive = Gold anomalously strong (Sell Signal), Negative = Gold anomalously weak (Buy Signal)
            'dxy_trend': 'NEUTRAL',
            'dxy_active': False
        }
        
        if not self.dxy_symbol or len(gold_df) < 25:
            return result
            
        # Fetch DXY Data matching Gold's timeframe
        timeframe = mt5.TIMEFRAME_M15 # Default
        if len(gold_df) > 1:
            diff = gold_df['time'].iloc[-1] - gold_df['time'].iloc[-2]
            if diff.total_seconds() <= 300: timeframe = mt5.TIMEFRAME_M5
            elif diff.total_seconds() >= 3600: timeframe = mt5.TIMEFRAME_H1
            
        rates = mt5.copy_rates_from_pos(self.dxy_symbol, timeframe, 0, len(gold_df))
        if rates is None or len(rates) == 0:
            return result
            
        result['dxy_active'] = True
        dxy_df = pd.DataFrame(rates)
        
        if len(dxy_df) < 20:
            return result
            
        # Calculate Rolling Correlation on Close prices (last 20 periods)
        min_len = min(len(gold_df), len(dxy_df))
        g_close = gold_df['close'].iloc[-min_len:].reset_index(drop=True)
        d_close = dxy_df['close'].iloc[-min_len:].reset_index(drop=True)
        
        corr = g_close.rolling(window=20).corr(d_close).iloc[-1]
        if pd.isna(corr): corr = 0.0
        
        result['dxy_correlation'] = corr
        
        # Calculate recent momentum (last 5 candles)
        g_trend = g_close.iloc[-1] - g_close.iloc[-5]
        d_trend = d_close.iloc[-1] - d_close.iloc[-5]
        
        # Normalize trends (Percent change)
        g_pct = g_trend / g_close.iloc[-5]
        d_pct = d_trend / d_close.iloc[-5]
        
        if d_pct > 0.0005: result['dxy_trend'] = 'UP'
        elif d_pct < -0.0005: result['dxy_trend'] = 'DOWN'
        
        # Institutional Z-Score Cointegration Spread (Logarithmic)
        # We use Log prices to linearize returns, neutralizing magnitude differences across assets.
        # Since Gold and DXY are inversely correlated, log addition corresponds to multiplication.
        spread = np.log(g_close) + np.log(d_close)
        
        # Calculate Z-Score over the rolling window (up to 50 periods)
        lookback = min(50, len(spread))
        rolling_mean = spread.rolling(window=lookback).mean()
        rolling_std = spread.rolling(window=lookback).std()
        
        if rolling_std.iloc[-1] == 0 or pd.isna(rolling_std.iloc[-1]):
            z_score = 0.0
        else:
            z_score = (spread.iloc[-1] - rolling_mean.iloc[-1]) / rolling_std.iloc[-1]
            
        # --- THE GOLDEN RULE (STRUCTURAL CORRELATION BREAK) ---
        # A high Z-Score is meaningless if Pearson Correlation is still perfectly inverse (e.g., -0.95).
        # That just means Gold is trending heavily, but it's still obeying the Dollar.
        # We only trade a true anomaly if the correlation breaks towards positive (e.g., > -0.5).
        if corr < -0.50:
            # Correlation is still healthy-inverse. This is a magnitude difference, not a true mispricing.
            # print(f"🛡️ Correlation Guard: Z-Score was {z_score:.2f} but Corr is {corr:.2f}. Anomaly VETOED.")
            z_score = 0.0
            
        # --- DXY VOLATILITY EXPANSION (CHOP GUARD) ---
        # If DXY is just drifting sideways, correlations will flip-flop meaninglessly.
        # We only want to arbitrage a divergence if real institutional money is moving DXY.
        d_tr = np.maximum(dxy_df['high'] - dxy_df['low'], 
               np.maximum(abs(dxy_df['high'] - dxy_df['close'].shift()), 
                          abs(dxy_df['low'] - dxy_df['close'].shift())))
                          
        d_current_atr = d_tr.iloc[-14:].mean()
        d_baseline_atr = d_tr.iloc[-50:-14].mean() if len(d_tr) >= 50 else d_current_atr
        
        # Volatility Ratio (e.g., 1.2x means ATR is 20% higher than baseline)
        dxy_volatility_ratio = d_current_atr / d_baseline_atr if d_baseline_atr > 0 else 1.0
        
        # If Volatility is contracting (ratio < 1.0), the market is chopping sideways.
        # We aggressively slash the Z-Score to prevent fake signals.
        if dxy_volatility_ratio < 1.0:
            # e.g., if ratio is 0.8, we multiply Z-Score by 0.5 (heavy penalty)
            penalty = max(0.0, dxy_volatility_ratio - 0.2) # Below 0.2 is dead flat = 0
            z_score_adj = z_score * penalty
            # print(f"📉 DXY Chop Guard: Volatility contracting ({dxy_volatility_ratio:.2f}x). Slashed Z-Score from {z_score:.2f} to {z_score_adj:.2f}")
            z_score = z_score_adj
            
        result['divergence_score'] = z_score
        
        # --- THE THIRD VARIABLE RISK (PANIC GUARD) ---
        # If global panic hits, BOTH Gold and DXY will spike (Safe Haven Convergence).
        # We proxy a VIX spike by checking if Gold's volatility (ATR) is exploding
        # AND both assets are ripping upwards simultaneously.
        
        # Calculate proxy volatility (ATR of the last 14 periods vs the ATR of the previous 50 periods)
        tr = np.maximum(gold_df['high'] - gold_df['low'], 
             np.maximum(abs(gold_df['high'] - gold_df['close'].shift()), 
                        abs(gold_df['low'] - gold_df['close'].shift())))
        
        current_atr = tr.iloc[-14:].mean()
        baseline_atr = tr.iloc[-50:-14].mean() if len(tr) >= 50 else current_atr
        
        volatility_expansion = current_atr / baseline_atr if baseline_atr > 0 else 1.0
        
        # If Volatility has expanded by > 50% AND both DXY and Gold are surging
        vix_spike = False
        if volatility_expansion > 1.5 and g_pct > 0.001 and d_pct > 0.001:
            vix_spike = True
            print(f"🌋 VIX PANIC GUARD ACTIVATED: Safe Haven Convergence Detected (Vol Expansion: {volatility_expansion:.2f}x). Suspending StatArb Shorts.")
            
        result['vix_spike'] = vix_spike
        
        return result
