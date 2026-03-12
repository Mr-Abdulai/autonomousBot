import pandas as pd
import numpy as np
import warnings
from datetime import datetime, timedelta

try:
    from sklearn.ensemble import HistGradientBoostingClassifier
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

class MLEngine:
    """
    Institutional Upgrade 3: Machine Learning Delta Engine.
    Uses a dynamic Gradient Boosting model (LightGBM equivalent) to predict 
    the probability that the price will be higher N candles from now.
    Trains dynamically on the last rolling window of data to adapt to regimes.
    """
    def __init__(self, target_lookforward=5, training_window=2000):
        self.target_lookforward = target_lookforward
        self.training_window = training_window
        self.model = None
        self.last_trained = None
        self.features = ['RSI_14', 'MACD', 'MACDh', 'STOCHk', 'STOCHd', 'ATR_14', 'close_to_ema50', 'close_to_vwap']
        
    def _prepare_data(self, df: pd.DataFrame):
        """Creates feature matrix and target labels."""
        data = df.copy()
        
        # Ensure base indicators exist
        if 'RSI_14' not in data.columns: return None, None
        
        # Calculate derived features
        data['close_to_ema50'] = (data['close'] - data['EMA_50']) / data['EMA_50']
        
        # VWAP approximation if VWAP isn't present
        if 'tick_volume' in data.columns:
            typical = (data['high'] + data['low'] + data['close']) / 3
            vwap_proxy = (typical * data['tick_volume']).rolling(window=20).sum() / data['tick_volume'].rolling(window=20).sum()
            data['close_to_vwap'] = (data['close'] - vwap_proxy) / vwap_proxy
        else:
            data['close_to_vwap'] = 0.0

        # Define Target: Will price be higher in N candles?
        data['target_price'] = data['close'].shift(-self.target_lookforward)
        data['target'] = (data['target_price'] > data['close']).astype(int)
        
        # Drop rows with NaNs (specifically the last N rows due to shift)
        data.dropna(subset=self.features + ['target'], inplace=True)
        
        return data[self.features], data['target']
        
    def train(self, df: pd.DataFrame):
        """Trains the model if sufficient data is available and enough time has passed."""
        if not SKLEARN_AVAILABLE: return False
        if len(df) < 500: return False # Need minimum data
        
        # Only retrain every hour (assuming M15 timeframe = 4 candles) to save CPU
        if self.last_trained and (datetime.now() - self.last_trained).total_seconds() < 3600:
            return True # Still valid
            
        train_df = df.iloc[-self.training_window:] if len(df) > self.training_window else df
        
        X, y = self._prepare_data(train_df)
        if X is None or len(X) < 100: return False
        
        # Check if we have both classes
        if len(np.unique(y)) < 2: return False
        
        self.model = HistGradientBoostingClassifier(
            max_iter=100, 
            learning_rate=0.05, 
            max_depth=5,
            random_state=42
        )
        
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            self.model.fit(X, y)
            
        self.last_trained = datetime.now()
        print(f"🧠 ML Delta Engine Trained: {len(X)} samples, predicting T+{self.target_lookforward} candles.")
        return True
        
    def predict_delta(self, df: pd.DataFrame) -> dict:
        """
        Predicts the Delta (Probability of Upward movement).
        Returns {'bullish_prob': 0.0-1.0, 'bearish_prob': 0.0-1.0, 'active': bool}
        """
        result = {'bullish_prob': 0.5, 'bearish_prob': 0.5, 'active': False}
        
        if not SKLEARN_AVAILABLE:
            result['error'] = "scikit-learn not installed"
            return result
            
        if self.model is None:
            success = self.train(df)
            if not success: return result
            
        # Prepare latest row
        latest = df.iloc[[-1]].copy()
        latest['close_to_ema50'] = (latest['close'] - latest['EMA_50']) / latest['EMA_50']
        
        # VWAP approximation
        if 'tick_volume' in latest.columns and len(df) >= 20:
             # Fast approximate VWAP for the single latest row using history
             history = df.iloc[-20:]
             typical = (history['high'] + history['low'] + history['close']) / 3
             vwap = (typical * history['tick_volume']).sum() / history['tick_volume'].sum()
             latest['close_to_vwap'] = (latest['close'] - vwap) / vwap
        else:
             latest['close_to_vwap'] = 0.0
             
        # Ensure features exist
        missing = [f for f in self.features if f not in latest.columns]
        if missing: return result
        
        X_pred = latest[self.features]
        
        try:
            probs = self.model.predict_proba(X_pred)[0]
            # Probabilities array: [P(class_0), P(class_1)] = [P(Down), P(Up)]
            result['bearish_prob'] = float(probs[0])
            result['bullish_prob'] = float(probs[1])
            result['active'] = True
        except Exception as e:
            print(f"ML Engine Prediction Error: {e}")
            
        return result
