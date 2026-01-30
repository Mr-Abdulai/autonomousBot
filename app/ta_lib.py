import pandas as pd
import numpy as np

class TALib:
    """
    Custom Technical Analysis Library using pure Pandas/Numpy.
    Replaces pandas_ta to avoid installation issues.
    """
    
    @staticmethod
    def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculates all standard indicators used by the Strategy.
        Mutates dataframe or returns new one with columns:
        RSI_14, EMA_50, EMA_200, ATR_14, BB_Upper, BB_Lower, 
        MACD, MACDs, MACDh, STOCHk, STOCHd.
        """
        # Ensure sufficient data
        if df is None or len(df) < 200:
            return df

        # RSI
        df['RSI_14'] = TALib.rsi(df['close'], 14)
        
        # EMAs
        df['EMA_50'] = TALib.ema(df['close'], 50)
        df['EMA_200'] = TALib.ema(df['close'], 200)
        
        # ATR
        df['ATR_14'] = TALib.atr(df, 14)
        
        # Bollinger Bands
        bb = TALib.bbands(df['close'])
        df['BB_Upper'] = bb['BBU']
        df['BB_Lower'] = bb['BBL']
        
        # MACD
        macd = TALib.macd(df['close'])
        df['MACD'] = macd['MACD']
        df['MACDs'] = macd['MACDs']
        df['MACDh'] = macd['MACDh']
        
        # Stochastic
        stoch = TALib.stoch(df)
        df['STOCHk'] = stoch['STOCHk']
        df['STOCHd'] = stoch['STOCHd']
        
        # Clean up NaNs created by indicators (optional, but good for safety)
        df.bfill(inplace=True)
        
        return df

    @staticmethod
    def rsi(series: pd.Series, length: int = 14) -> pd.Series:
        delta = series.diff()
        # gain = (delta.where(delta > 0, 0)).rolling(window=length).mean()
        # loss = (-delta.where(delta < 0, 0)).rolling(window=length).mean()
        
        # Use exponential moving average for wilder's RSI if preferred, 
        # but simple rolling is robust enough for this context.
        # Let's match standard Wilder's RSI usually:
        gain = (delta.where(delta > 0, 0)).ewm(alpha=1/length, adjust=False).mean()
        loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/length, adjust=False).mean()
        
        rs = gain / loss
        return 100 - (100 / (1 + rs))

    @staticmethod
    def ema(series: pd.Series, length: int) -> pd.Series:
        return series.ewm(span=length, adjust=False).mean()

    @staticmethod
    def atr(df: pd.DataFrame, length: int = 14) -> pd.Series:
        high = df['high']
        low = df['low']
        close = df['close']
        prev_close = close.shift(1)
        
        tr1 = high - low
        tr2 = (high - prev_close).abs()
        tr3 = (low - prev_close).abs()
        
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        # return tr.rolling(window=length).mean() # SMMA/RMA typically used, but simple rolling or ewm ok.
        # Better to use EWM for ATR to match standard
        return tr.ewm(alpha=1/length, adjust=False).mean()

    @staticmethod
    def bbands(series: pd.Series, length: int = 20, std: int = 2) -> pd.DataFrame:
        ma = series.rolling(window=length).mean()
        std_dev = series.rolling(window=length).std()
        upper = ma + (std_dev * std)
        lower = ma - (std_dev * std)
        return pd.DataFrame({'BBM': ma, 'BBU': upper, 'BBL': lower})

    @staticmethod
    def macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
        ema_fast = series.ewm(span=fast, adjust=False).mean()
        ema_slow = series.ewm(span=slow, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        hist = macd_line - signal_line
        return pd.DataFrame({'MACD': macd_line, 'MACDs': signal_line, 'MACDh': hist})

    @staticmethod
    def stoch(df: pd.DataFrame, k: int = 14, d: int = 3, smooth_k: int = 3) -> pd.DataFrame:
        # Fast Stochastic
        low_min = df['low'].rolling(window=k).min()
        high_max = df['high'].rolling(window=k).max()
        
        # Avoid division by zero
        denom = high_max - low_min
        denom = denom.replace(0, 0.0001) 
        
        fast_k = 100 * (df['close'] - low_min) / denom
        
        # Slow Stochastic (Smooth Fast K)
        stoch_k = fast_k.rolling(window=smooth_k).mean()
        stoch_d = stoch_k.rolling(window=d).mean()
        
        return pd.DataFrame({'STOCHk': stoch_k, 'STOCHd': stoch_d})

    @staticmethod
    def identify_fractals(df: pd.DataFrame) -> pd.DataFrame:
        """
        Bill Williams Fractals (5-bar pattern).
        Returns df with 'fractal_high' and 'fractal_low' boolean columns.
        Note: Fractal is confirmed 2 bars later.
        """
        # We need 5 bars window. The "Fractal" is at the center (index i).
        # Shift -2 means we are looking at future bars relative to i, 
        # but in realtime we just check if i-2 was a fractal relative to i, i-1, i-3, i-4.
        
        # Explicit copy to prevent SettingWithCopyWarning on slices
        df = df.copy()
        
        # Vectorized implementation for speed
        # Highs
        h = df['high']
        is_up = (h > h.shift(1)) & (h > h.shift(2)) & \
                (h > h.shift(-1)) & (h > h.shift(-2))
                
        # Lows
        l = df['low']
        is_down = (l < l.shift(1)) & (l < l.shift(2)) & \
                  (l < l.shift(-1)) & (l < l.shift(-2))
                  
        # Use .loc to avoid SettingWithCopyWarning
        df.loc[:, 'fractal_high'] = is_up
        df.loc[:, 'fractal_low'] = is_down
        
        # Fill NA (created by shift) with False
        df.loc[:, 'fractal_high'] = df['fractal_high'].fillna(False)
        df.loc[:, 'fractal_low'] = df['fractal_low'].fillna(False)
        
        return df

    @staticmethod
    def calculate_vwap(df: pd.DataFrame) -> float:
        """
        PHASE 5B: Volume-Weighted Average Price
        Institutional support/resistance level
        """
        if 'tick_volume' not in df.columns or len(df) < 1:
            return df['close'].iloc[-1] if len(df) > 0 else 0.0
        
        typical_price = (df['high'] + df['low'] + df['close']) / 3
        vwap = (typical_price * df['tick_volume']).cumsum() / df['tick_volume'].cumsum()
        return vwap.iloc[-1]
    
    @staticmethod
    def calculate_supertrend(df: pd.DataFrame, period: int = 10, multiplier: float = 3.0) -> dict:
        """
        PHASE 5B: SuperTrend Indicator
        Dynamic support/resistance based on ATR
        Returns {'trend': 'UP'/'DOWN', 'level': price, 'signal': 'BUY'/'SELL'/'HOLD'}
        """
        if len(df) < period + 1:
            return {'trend': 'NEUTRAL', 'level': 0.0, 'signal': 'HOLD'}
        
        # Calculate ATR
        atr = TALib.atr(df, period)
        
        # Calculate basic upper and lower bands
        hl_avg = (df['high'] + df['low']) / 2
        upper_band = hl_avg + (multiplier * atr)
        lower_band = hl_avg - (multiplier * atr)
        
        # Initialize supertrend
        supertrend = pd.Series(index=df.index, dtype=float)
        trend = pd.Series(index=df.index, dtype=int)
        
        # First value
        supertrend.iloc[0] = lower_band.iloc[0]
        trend.iloc[0] = 1  # Assume uptrend initially
        
        for i in range(1, len(df)):
            # Update bands based on previous supertrend
            if df['close'].iloc[i] > supertrend.iloc[i-1]:
                trend.iloc[i] = 1  # Uptrend
                supertrend.iloc[i] = max(lower_band.iloc[i], supertrend.iloc[i-1])
            else:
                trend.iloc[i] = -1  # Downtrend
                supertrend.iloc[i] = min(upper_band.iloc[i], supertrend.iloc[i-1])
        
        current_trend = 'UP' if trend.iloc[-1] == 1 else 'DOWN'
        current_level = supertrend.iloc[-1]
        
        # Generate signal (trend change)
        signal = 'HOLD'
        if len(trend) > 1:
            if trend.iloc[-1] == 1 and trend.iloc[-2] == -1:
                signal = 'BUY'  # Trend flipped to up
            elif trend.iloc[-1] == -1 and trend.iloc[-2] == 1:
                signal = 'SELL'  # Trend flipped to down
        
        return {
            'trend': current_trend,
            'level': current_level,
            'signal': signal
        }
    
    @staticmethod
    def calculate_rvi(df: pd.DataFrame, period: int = 14) -> float:
        """
        PHASE 5B: Relative Vigor Index
        Measures momentum/conviction behind price moves
        Range: -1 to +1 (like RSI but centered at 0)
        Positive = Bullish momentum, Negative = Bearish momentum
        """
        if len(df) < period + 10:
            return 0.0
        
        # RVI formula: (Close - Open) / (High - Low)
        # Smoothed with SMA
        close_open = df['close'] - df['open']
        high_low = df['high'] - df['low']
        
        # Avoid division by zero
        high_low = high_low.replace(0, 0.0001)
        
        # Calculate numerator and denominator with SMA smoothing
        num = close_open.rolling(window=period).mean()
        denom = high_low.rolling(window=period).mean()
        
        rvi = num / denom
        
        # Normalize to -1 to +1 range
        rvi = rvi.clip(-1, 1)
        
        return rvi.iloc[-1] if not pd.isna(rvi.iloc[-1]) else 0.0
