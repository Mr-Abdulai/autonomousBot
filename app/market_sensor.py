import pandas as pd
import MetaTrader5 as mt5
from datetime import datetime
from .ta_lib import TALib
from .smc import SMCEngine
from .news_harvester import NewsHarvester

class MarketSensor:
    def __init__(self, symbol="EURUSD", timeframe=mt5.TIMEFRAME_M15):
        self.symbol = symbol
        self.timeframe = timeframe
        self.smc = SMCEngine() # Initialize SMC Engine
        self.news = NewsHarvester() # Initialize News Engine
    
    def initialize(self) -> bool:
        """Initializes the MT5 connection and resolves specific symbol name."""
        if not mt5.initialize():
            print(f"MT5 initialization failed: {mt5.last_error()}")
            return False
        
        # Resolve Symbol (Handle Suffixes)
        resolved_symbol = self._resolve_symbol(self.symbol)
        if not resolved_symbol:
            print(f"CRITICAL: Symbol {self.symbol} not found in Market Watch or database.")
            # Attempt to show available similiar symbols
            similar = mt5.symbols_get(group=f"*{self.symbol}*")
            if similar:
                names = [s.name for s in similar]
                print(f"Did you mean one of these? {names}")
            return False
            
        print(f"Symbol Resolved: {self.symbol} -> {resolved_symbol}")
        self.symbol = resolved_symbol # Update to the specific broker symbol
                
        if not mt5.symbol_select(self.symbol, True):
            print(f"Failed to select symbol {self.symbol}")
            return False
                
        return True

    def _resolve_symbol(self, base_symbol: str) -> str:
        """
        Attempts to find the broker-specific symbol name.
        Example: 'XAUUSD' -> 'XAUUSDm', 'Gold', etc.
        """
        # 1. Try exact match
        info = mt5.symbol_info(base_symbol)
        if info is not None:
            return base_symbol
            
        # 2. Try common suffixes
        suffixes = ["m", "pro", "ecn", ".a", "_otc"]
        for suffix in suffixes:
            trial = f"{base_symbol}{suffix}"
            if mt5.symbol_info(trial) is not None:
                return trial
                
        # 3. Search by partial match (Expensive but robust)
        # Returns all symbols containing the base_name
        all_symbols = mt5.symbols_get()
        if all_symbols:
            for s in all_symbols:
                if base_symbol in s.name:
                    # Heuristic: return the first visible one, or just the first match
                    # Ideally we want the one that is 'tradable'
                    return s.name
        
        return None

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculates RSI, EMA, ATR using pure pandas."""
        # Ensure df is sorted by time
        df = df.sort_values('time').reset_index(drop=True)
        close = df['close']
        high = df['high']
        low = df['low']

        # 1. EMA 50 & 200
        df['EMA_50'] = close.ewm(span=50, adjust=False).mean()
        df['EMA_200'] = close.ewm(span=200, adjust=False).mean()

        # 2. RSI 14
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).ewm(alpha=1/14, adjust=False).mean()
        loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/14, adjust=False).mean()
        rs = gain / loss
        df['RSI_14'] = 100 - (100 / (1 + rs))

        # 3. ATR 14
        prev_close = close.shift(1)
        tr1 = high - low
        tr2 = (high - prev_close).abs()
        tr3 = (low - prev_close).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        df['ATR_14'] = tr.ewm(alpha=1/14, adjust=False).mean()

        # 4. Bollinger Bands (20, 2)
        sma_20 = close.rolling(window=20).mean()
        std_20 = close.rolling(window=20).std()
        df['BB_Upper'] = sma_20 + (std_20 * 2)
        df['BB_Lower'] = sma_20 - (std_20 * 2)
        
        # 5. MACD (12, 26, 9)
        ema_12 = close.ewm(span=12, adjust=False).mean()
        ema_26 = close.ewm(span=26, adjust=False).mean()
        df['MACD'] = ema_12 - ema_26
        df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
        df['MACD_Hist'] = df['MACD'] - df['MACD_Signal']
        
        return df

    def get_market_data(self, n_candles: int = 500) -> pd.DataFrame:
        """
        Fetches n_candles from MT5, calculates indicators.
        Returns DataFrame with 'time', 'open', 'high', 'low', 'close', 'tick_volume',
        'RSI_14', 'EMA_50', 'EMA_200', 'ATR_14', 'BB_Upper', 'BB_Lower', 'MACD', 'MACD_Signal'.
        """
        if not self.initialize():
            raise ConnectionError("Could not connect to MT5 or find symbol.")

        # Copy rates from MT5
        rates = mt5.copy_rates_from_pos(self.symbol, self.timeframe, 0, n_candles)
        
        if rates is None or len(rates) == 0:
            raise ValueError("No data received from MT5.")

        # Create DataFrame
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        
        # Calculate Indicators (Custom)
        df = self.calculate_indicators(df)
        
        return df
        
    def fetch_mtf_data(self, n_candles: int = 500) -> dict:
        """
        Fetches M15, H1, and H4 data for the Matrix Analysis.
        Returns: {'M15': df, 'H1': df, 'H4': df}
        """
        if not self.initialize():
            raise ConnectionError("MT5 Init Failed")
            
        # Helper to fetch and clean
        def _fetch(tf):
            rates = mt5.copy_rates_from_pos(self.symbol, tf, 0, n_candles)
            if rates is None or len(rates) == 0: return pd.DataFrame()
            df = pd.DataFrame(rates)
            df['time'] = pd.to_datetime(df['time'], unit='s')
            df.dropna(inplace=True)
            return df
            
        return {
            'BASE': _fetch(self.timeframe), # BASE (M5)
            'HTF1': _fetch(mt5.TIMEFRAME_M15), # M15
            'HTF2': _fetch(mt5.TIMEFRAME_H4) # H4
        }

    def calculate_indicators(self, df):
        """
        Adds Technical Indicators to the DF using custom TA lib.
        """
        # 1. Trend
        df['EMA_50'] = TALib.ema(df['close'], 50)
        df['EMA_200'] = TALib.ema(df['close'], 200)
        
        # 2. Momentum
        df['RSI_14'] = TALib.rsi(df['close'], 14)
        
        stoch = TALib.stoch(df)
        df['STOCHk'] = stoch['STOCHk']
        df['STOCHd'] = stoch['STOCHd']
        
        macd = TALib.macd(df['close'])
        df['MACD'] = macd['MACD']
        df['MACDs'] = macd['MACDs']
        df['MACDh'] = macd['MACDh']
        
        # 3. Volatility
        bb = TALib.bbands(df['close'])
        df['BB_Upper'] = bb['BBU']
        df['BB_Lower'] = bb['BBL']
        
        df['ATR_14'] = TALib.atr(df, 14)
        
        return df

    def get_trend_data(self, timeframe, n_candles=200):
        """Helper to get simple trend state for a timeframe."""
        rates = mt5.copy_rates_from_pos(self.symbol, timeframe, 0, n_candles)
        if rates is None or len(rates) == 0:
            return "Unknown"
        
        df = pd.DataFrame(rates)
        close = df['close']
        
        # EMA Settings Logic
        if timeframe == mt5.TIMEFRAME_M15:
            # Fast Scalping Settings (13/50)
            fast_ema_period = 13
            slow_ema_period = 50
        else:
            # Standard Macro Settings (50/200)
            fast_ema_period = 50
            slow_ema_period = 200

        ema_fast = close.ewm(span=fast_ema_period, adjust=False).mean().iloc[-1]
        ema_slow = close.ewm(span=slow_ema_period, adjust=False).mean().iloc[-1]
        current = close.iloc[-1]
        
        # Strict Alignment Logic
        status = "Ranging"
        debug_suffix = f"({ema_fast:.5f}/{ema_slow:.5f})"
        
        if ema_fast > ema_slow:
            if current > ema_fast:
                status = "Bullish" # Strong Uptrend
            elif current > ema_slow:
                status = "Bullish (Pullback)" # Buying Opportunity
            else:
                 status = "Bullish (Broken Structure)" # Warning
        elif ema_fast < ema_slow:
            if current < ema_fast:
                 status = "Bearish" # Strong Downtrend
            elif current < ema_slow:
                 status = "Bearish (Pullback)" # Selling Opportunity
            else:
                 status = "Bearish (Broken Structure)" # Warning
        
        return f"{status} {debug_suffix}"

    def get_fractal_structure(self, df):
        """
        Analyzes the last known Fractals to determine Market Structure.
        Replaces Candlestick Patterns with Geometric Breakouts.
        Returns: { 'signal': 'BREAK_UP'|'BREAK_DOWN'|'SWEEP_UP'|'SWEEP_DOWN'|'NONE', 'level': float }
        """
        # 1. Identify Fractals
        df = TALib.identify_fractals(df)
        latest = df.iloc[-1]
        current_close = latest['close']
        
        # Find the most recent VALID Confirm Fractals (ignoring the last 2 bars which can't be fractals yet)
        # We slice [:-2] to be safe as fractal needs 2 future bars to confirm.
        valid_history = df.iloc[:-2]
        
        last_up_fractal = valid_history[valid_history['fractal_high']].iloc[-1] if any(valid_history['fractal_high']) else None
        last_down_fractal = valid_history[valid_history['fractal_low']].iloc[-1] if any(valid_history['fractal_low']) else None
        
        signal = "NONE"
        level = 0.0
        
        # CHECK BREAKOUTS (Trend Mode)
        # Price CLOSES above the last Fractal High -> Bullish Breakout
        if last_up_fractal is not None:
            res_level = last_up_fractal['high']
            if current_close > res_level and df.iloc[-2]['close'] <= res_level: # Fresh Break
                signal = "BREAK_UP"
                level = res_level

        # Price CLOSES below the last Fractal Low -> Bearish Breakout
        if last_down_fractal is not None:
             sup_level = last_down_fractal['low']
             if current_close < sup_level and df.iloc[-2]['close'] >= sup_level: # Fresh Break
                 signal = "BREAK_DOWN"
                 level = sup_level
                 
        # CHECK SWEEPS (Range Mode - Advanced)
        # Sweep = Hit Level but Close Inside (This requires looking at High/Low vs Close)
        # For simplicity, we just return the Breakout Signal for now, 
        # and let the Logic Engine decide if it's a Break (Trend) or Fakeout (Range) based on Hurst.
        
        return signal, level

    def get_latest_fractal_levels(self, df):
        """
        Returns the price of the last CONFIRMED Up and Down Fractals.
        Used for Structural Trailing Stops.
        Returns: {'resistance': float, 'support': float}
        """
        # Ensure fractals are calculated
        if 'fractal_high' not in df.columns:
            df = TALib.identify_fractals(df)
            
        # Valid History (Excluding last 2 bars which are unconfirmed)
        # Note: indentify_fractals uses forward shifting, so the boolean is effectively 'confirmed' 
        # relative to the future, but in realtime simulation we only know it 2 bars later.
        # But 'fractal_high' column is aligned to the *candle that is the high*.
        # So we just search the past.
        
        # We need to make sure we don't peek into the future if this was backtesting, 
        # but in live mode 'df' is history.
        
        # Latest Confirmable Fractal is at index -3 or earlier.
        # Because we need i+1 and i+2 to confirm i.
        valid_range = df.iloc[:-2] 
        
        last_resistance = 0.0
        last_support = 0.0
        
        # Search backwards
        up_fractals = valid_range[valid_range['fractal_high']]
        if not up_fractals.empty:
            last_resistance = up_fractals.iloc[-1]['high']
            
        down_fractals = valid_range[valid_range['fractal_low']]
        if not down_fractals.empty:
            last_support = down_fractals.iloc[-1]['low']
            
        return {'resistance': last_resistance, 'support': last_support}





            
    def check_technical_confluence(self):
        """
        Checks for Strong Technical Confluence (to bypass SMC requirement).
        Criteria (2+ Indicators):
        - BUY: Price > EMA50 AND (MACD > Signal OR RSI > 50) AND MACD > 0
        - SELL: Price < EMA50 AND (MACD < Signal OR RSI < 50) AND MACD < 0
        Returns: Tuple (bool, str) -> (is_confluent, reason)
        """
        try:
            df = self.get_market_data()
            latest = df.iloc[-1]
            
            # Extract Values
            close = latest['close']
            ema50 = latest['EMA_50']
            ema200 = latest['EMA_200']
            macd = latest['MACD']
            signal = latest['MACDs']
            rsi = latest['RSI_14']
            
            score = 0
            reasons = []
            
            # --- BULLISH CHECK ---
            if close > ema50:
                if macd > signal:
                    score += 1
                    reasons.append("MACD Bullish Cross")
                if rsi > 50 and rsi < 75:
                    score += 1
                    reasons.append("RSI Bullish Momentum")
                if close > ema200:
                    score += 1
                    reasons.append("Price > EMA200")
                    
                if score >= 2:
                    return True, f"[TECHNICAL CONFLUENCE: BULLISH] {' + '.join(reasons)}"

            # --- BEARISH CHECK ---
            elif close < ema50:
                if macd < signal:
                    score += 1
                    reasons.append("MACD Bearish Cross")
                if rsi < 50 and rsi > 25:
                    score += 1
                    reasons.append("RSI Bearish Momentum")
                if close < ema200:
                    score += 1
                    reasons.append("Price < EMA200")
                    
                if score >= 2:
                    return True, f"[TECHNICAL CONFLUENCE: BEARISH] {' + '.join(reasons)}"

            return False, "Weak Technicals"
            
        except Exception as e:
            print(f"Confluence Check Error: {e}")
            return False, "Error"

    def get_market_summary(self):
        """
        Returns a human-readable summary of the market state for the AI.
        Includes Trend, SMC Structure, Indicators, and FUNDAMENTALS.
        """
        # We need the full dataframe for SMC
        df = self.get_market_data(n_candles=500)
        if df is None or df.empty: return "Market Data Unavailable"
        
        # Calculate Indicators 
        df = TALib.calculate_indicators(df) 
        latest = df.iloc[-1]
        
        # --- SMC ANALYSIS ---
        smc_data = self.smc.calculate_smc(df)
        
        # Zero Trust OB Filter
        current_price = latest['close']
        ob_str = "None (Waiting for Price to Reach Zone)"
        if "order_blocks" in smc_data and smc_data["order_blocks"]:
            ob_list = []
            for ob in smc_data["order_blocks"]:
                p_top = ob['price_top']
                p_bot = ob['price_bottom']
                if p_bot <= current_price <= p_top:
                    ob_list.append(f"{ob['type']} @ {p_bot:.5f}-{p_top:.5f} [INSIDE_ZONE (READY)]")
            if ob_list:
                ob_str = " | ".join(ob_list)
        
        # --- NEWS ANALYSIS ---
        news_summary = self.news.fetch_upcoming_news()
        
        summary = f"""
MARKET STATUS REPORT ({self.symbol})
Price: {latest['close']}
EMA_50: {latest['EMA_50']:.5f} | EMA_200: {latest['EMA_200']:.5f}
RSI: {latest['RSI_14']:.1f}
ATR: {latest['ATR_14']:.5f}
MACD: {latest['MACD']:.5f} (Signal: {latest['MACDs']:.5f})
Stochastic: K={latest['STOCHk']:.1f}, D={latest['STOCHd']:.1f}

SMC STRUCTURE:
Trend: {smc_data.get('structure', 'Unknown')}
Active Order Blocks (Unmitigated): {ob_str}

FUNDAMENTAL CONTEXT:
{news_summary}
"""
        return summary
    def get_latest_indicators(self) -> dict:
        """
        Returns a dictionary of the latest calculated indicators.
        Used for dashboard visualization.
        """
        try:
            df = self.get_market_data()
            latest = df.iloc[-1]
            
            # Fetch Macro Trends
            trend_d1 = self.get_trend_data(mt5.TIMEFRAME_D1)
            trend_h4 = self.get_trend_data(mt5.TIMEFRAME_H4)
            trend_m15 = self.get_trend_data(mt5.TIMEFRAME_M15)
            
            # Fetch Spread
            symbol_info = mt5.symbol_info(self.symbol)
            spread = symbol_info.spread if symbol_info else 0

            return {
                "close": float(latest['close']),
                "rsi": float(latest['RSI_14']),
                "ema_50": float(latest['EMA_50']),
                "ema_200": float(latest['EMA_200']),
                "atr": float(latest['ATR_14']),
                "bb_upper": float(latest['BB_Upper']),
                "bb_lower": float(latest['BB_Lower']),
                "macd": float(latest['MACD']),
                "macd_signal": float(latest['MACDs']),
                "trend_d1": trend_d1,
                "spread": spread,
                "trend_h4": trend_h4,
                "trend_m15": trend_m15,
                "timestamp": str(latest['time'])
            }

        except:
            return {}

if __name__ == "__main__":
    # Test run
    sensor = MarketSensor()
    try:
        print(sensor.get_market_summary())
        mt5.shutdown()
    except Exception as e:
        print(e)
