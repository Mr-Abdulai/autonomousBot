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
