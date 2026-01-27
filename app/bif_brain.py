import numpy as np
import pandas as pd
import math
from typing import Dict, Any, Tuple
import logging

# Configure Logging for BIF
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("BIF_BRAIN")

# Try importing Advanced Math Libs
try:
    from hmmlearn.hmm import GMMHMM
    from scipy.stats import entropy
    from sklearn.preprocessing import StandardScaler
    ML_AVAILABLE = True
except ImportError as e:
    logger.warning(f"BIF Warning: Advanced ML libs missing ({e}). Running in Degraded Mode.")
    ML_AVAILABLE = False

class BIFBrain:
    """
    Phase 69: The Alpha Brain.
    Bayesian Information Fusion (BIF) Engine.
    
    Responsibilities:
    1. Decode Market Regime (HMM).
    2. Measure Signal Quality (Shannon Entropy).
    3. Measure Trend Persistence (Hurst Exponent).
    
    Returns:
    - 'regime': 0 (Range), 1 (Trend), 2 (Volatility)
    - 'entropy': 0.0 - 1.0 (Low = Order, High = Chaos)
    - 'hurst': 0.0 - 1.0 (<0.5 Mean Rev, >0.5 Trend)
    """
    
    def __init__(self):
        self.hmm_model = None
        self.scaler = None
        if ML_AVAILABLE:
            # 3 State Model: Range, Trend, Volatility
            # n_mix = 2 (Gaussian Mixtures per state)
            self.hmm_model = GMMHMM(n_components=3, n_mix=2, covariance_type="full", n_iter=100, random_state=42)
            self.scaler = StandardScaler()

    def analyze_market_state(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Main Entry Point.
        Accepts DataFrame with 'close'.
        Returns Dictionary of BIF Metrics.
        """
        if df is None or len(df) < 100:
            return {"status": "INSUFFICIENT_DATA"}
            
        # 1. Prepare Data
        # Log Returns
        df['log_ret'] = np.log(df['close'] / df['close'].shift(1))
        # Rolling Volatility (scaled)
        df['volatility'] = df['log_ret'].rolling(window=20).std()
        
        df = df.dropna()
        
        # 2. Compute Metrics
        hurst_val = self._calculate_hurst(df['log_ret'].values)
        entropy_val = self._calculate_entropy(df['log_ret'].values)
        
        regime = "UNKNOWN"
        regime_id = -1
        
        if ML_AVAILABLE and len(df) > 200:
            regime_id, regime_probs = self._decode_hmm_regime(df)
            # Map ID to Concept (This requires semantic mapping, usually heuristic based on variance)
            # For now, we return the ID.
        
        return {
            "hurst": round(hurst_val, 3),
            "entropy": round(entropy_val, 3),
            "regime_id": regime_id,
            "ml_active": ML_AVAILABLE
        }

    def analyze_mtf_regime(self, data_dict: Dict[str, pd.DataFrame]) -> Dict[str, Any]:
        """
        Matrix Analysis: Calculates Hurst/Entropy for M15, H1, H4.
        Returns Composite Alignment Score (-1.0 to 1.0).
        """
        results = {}
        alignment_score = 0
        
        # 1. Analyze Each Timeframe
        for tf, df in data_dict.items():
            if df.empty:
                results[tf] = {'hurst': 0.5, 'entropy': 1.0} # Default to Random
                continue
                
            stats = self.analyze_market_state(df)
            results[tf] = stats
            
        # 2. Compute Alignment
        # Core Thesis: Lower TF (M15) provides Signal, Higher TF (H1) provides Permission.
        
        m15_hurst = results.get('M15', {}).get('hurst', 0.5)
        h1_hurst = results.get('H1', {}).get('hurst', 0.5)
        h4_hurst = results.get('H4', {}).get('hurst', 0.5)
        
        # Base Score from M15
        if m15_hurst > 0.55: # M15 Trending
            # Check H1 Permission
            if h1_hurst > 0.5:
                alignment_score += 0.5 # H1 Supports Trend
                
                # Check H4 Bonus
                if h4_hurst > 0.5:
                    alignment_score += 0.5 # H4 Supports Trend
                elif h4_hurst < 0.45:
                     alignment_score -= 0.2 # H4 Mean Reverting (Headwind)
            else:
                # H1 is Mean Reverting (Blocking M15 Trend)
                alignment_score -= 1.0 # VETO
                
        elif m15_hurst < 0.45: # M15 Mean Reverting
            # Range Trading on M15 is risky unless H1 is also Ranging
            if h1_hurst < 0.5:
                alignment_score += 0.5
            else:
                alignment_score -= 0.5 # H1 Trending (Dangerous to fade)

        return {
             "mtf_stats": results,
             "alignment_score": alignment_score, # > 0.5 means Safe to Trade
             "summary": f"M15_H:{m15_hurst} | H1_H:{h1_hurst} | Score:{alignment_score}"
        }

    def _calculate_entropy(self, data: np.ndarray, bins: int = 20) -> float:
        """
        Calculates Shannon Entropy of the return distribution.
        Low Entropy = Fat Tails / Ordered Movement (Trend).
        High Entropy = Gaussian Noise (Random Walk).
        """
        try:
            hist, _ = np.histogram(data, bins=bins, density=True)
            # Remove zeros for log calculation
            hist = hist[hist > 0]
            if not ML_AVAILABLE:
                 # Manually calculate if scipy missing
                 ent = -np.sum(hist * np.log(hist))
            else:
                 ent = entropy(hist)
            
            # Normalize by Max Entropy (log of bins)
            max_ent = np.log(bins)
            normalized_ent = ent / max_ent
            return float(normalized_ent)
        except Exception as e:
            logger.error(f"Entropy Error: {e}")
            return 1.0 # Assume Maximum Chaos on Error

    def _calculate_hurst(self, ts: np.ndarray) -> float:
        """
        Calculates Hurst Exponent using rigorous Rescaled Range (R/S) Analysis.
        Returns:
            H < 0.5: Mean Reverting (Anti-persistent)
            H ~ 0.5: Random Walk (GBM)
            H > 0.5: Trending (Persistent)
        """
        try:
            ts = np.array(ts)
            # Hedge Fund Standard: Use sufficient lags to capture fractal structure
            min_lag = 10
            max_lag = min(len(ts) // 2, 100) # At least half the series
            lags = range(min_lag, max_lag)
            
            rs_values = []
            
            for lag in lags:
                # 1. Split time series into chunks of size 'lag'
                # For simplicity here, we just take the first 'lag' points, then sliding window?
                # Standard R/S: Calculate R/S for chunks of size n.
                # Here we use a rolling window approach for efficiency on small arrays.
                
                # Get sub-series
                chunk = ts[-lag:] # Use most recent 'lag' points
                
                # Calculate Mean
                m = np.mean(chunk)
                
                # Deviations
                y = chunk - m
                
                # Cumulative Deviations
                z = np.cumsum(y)
                
                # Range
                r = np.max(z) - np.min(z)
                
                # Standard Deviation
                s = np.std(chunk)
                
                if s == 0:
                    rs_values.append(0)
                else:
                    rs_values.append(r / s)
            
            # Filter valid (log of 0 is -inf)
            valid_idx = [i for i, x in enumerate(rs_values) if x > 0]
            if len(valid_idx) < 3:
                return 0.5
                
            y = np.log(np.array(rs_values)[valid_idx])
            x = np.log(np.array(lags)[valid_idx])
            
            # Polyfit line
            slope, _ = np.polyfit(x, y, 1)
            
            return float(slope)
        except Exception as e:
            logger.error(f"Hurst Error: {e}")
            return 0.5

    def _decode_hmm_regime(self, df: pd.DataFrame) -> Tuple[int, np.ndarray]:
        """
        Trains GMM-HMM on recent data and decodes the current state.
        Feature Vector: [LogReturns, Volatility]
        """
        try:
            # Features
            X = df[['log_ret', 'volatility']].values
            
            # Scale
            X_scaled = self.scaler.fit_transform(X)
            
            # Train (Fit on history)
            self.hmm_model.fit(X_scaled)
            
            # Decode (Viterbi Path)
            hidden_states = self.hmm_model.predict(X_scaled)
            
            # Get current state (last one)
            current_state = hidden_states[-1]
            
            # Get Probabilities
            probs = self.hmm_model.predict_proba(X_scaled)[-1]
            
            return int(current_state), probs
            
        except Exception as e:
            logger.error(f"HMM Error: {e}")
            return -1, []

if __name__ == "__main__":
    # Unit Test / Playground
    print("Testing BIF Brain...")
    brain = BIFBrain()
    
    # Generate Mock Data (Random Walk)
    dates = pd.date_range(start="2023-01-01", periods=500, freq="15min")
    close = np.cumprod(1 + np.random.normal(0, 0.001, 500)) # GBM
    df = pd.DataFrame({"close": close}, index=dates)
    
    res = brain.analyze_market_state(df)
    print(f"Result (Random Walk): {res}")
    
    # Generate Trend Data
    trend = np.linspace(1, 1.2, 500)
    close_trend = close * trend
    df_trend = pd.DataFrame({"close": close_trend}, index=dates)
    
    res_trend = brain.analyze_market_state(df_trend)
    print(f"Result (Trend): {res_trend}")
