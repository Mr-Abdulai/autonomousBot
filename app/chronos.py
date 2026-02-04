import numpy as np
import pandas as pd
import logging
from typing import List, Dict

class ChronosWeaver:
    """
    Project Chronos: The Generative Simulation Engine.
    'The Weaver' generates synthetic futures (parallel timelines).
    """
    def __init__(self, history_df: pd.DataFrame):
        self.history = history_df
        # Pre-calc returns for bootstrapping
        self.history['returns'] = self.history['close'].pct_change()
        self.history['log_returns'] = np.log(self.history['close'] / self.history['close'].shift(1))
        
    def generate_monte_carlo(self, current_price: float, atr: float, drift: float, n_futures=100, horizon=10) -> np.ndarray:
        """
        LITE ENGINE: Random Walk with Drift.
        Generates n_futures paths of length horizon.
        Drift is derived from recent EMA slope.
        """
        print(f"🔮 Chronos Lite (Monte Carlo): Generating {n_futures} paths with Drift {drift:.5f}...", flush=True)
        dt = 1 # time step
        # Sigma (Volatility) approximated from ATR
        # ATR is absolute movement. Approx % vol = ATR / Price
        sigma = (atr / current_price) 
        mu = drift # Drift factor
        
        # S_t = S_0 * exp((mu - 0.5*sigma^2)*t + sigma*W_t)
        # We simulate log returns
        
        futures = np.zeros((n_futures, horizon))
        
        for i in range(n_futures):
            # Random shocks (Brownian Motion)
            shocks = np.random.normal(0, 1, horizon)
            path = [current_price]
            
            for t in range(horizon):
                # Simple geometric brownian motion step
                # price = prev * (1 + mu + sigma * shock)
                prev = path[-1]
                change = prev * (mu + sigma * shocks[t])
                path.append(prev + change)
                
            futures[i, :] = path[1:] # Exclude S0
            
        return futures

    def generate_historical_echoes(self, current_features: dict, n_futures=100, horizon=10) -> np.ndarray:
        """
        PRO ENGINE: Regime-Based Bootstrapping.
        Finds historical segments that look like "Now" and projects their outcomes.
        """
        # 1. Identify "Now"
        # Features: Hurst, RSI, Volatility (ATR/Price)
        # We need these features pre-calculated in history to match efficiently.
        # Computing them on the fly for 5000 candles is slow.
        # Fallback: Simple Volatility Matching if features not in DF.
        
        # For this version, we'll use a simplified correlation match or just volatility match.
        # Let's use Volatility Clustering (GARCH-lite).
        
        current_vol = current_features.get('volatility', 0.001)
        
        # Find all segments in history with similar volatility (+/- 20%)
        # Rolling volatility of length 10
        if 'rolling_vol' not in self.history.columns:
            self.history['rolling_vol'] = self.history['returns'].rolling(10).std()
            
        matches = self.history[
            (self.history['rolling_vol'] > current_vol * 0.8) & 
            (self.history['rolling_vol'] < current_vol * 1.2)
        ]
        
        if len(matches) < n_futures:
            # Fallback to random sampling if no regime match
            matches = self.history
            
        # Sample actual return sequences
        futures = np.zeros((n_futures, horizon))
        valid_indices = matches.index[matches.index < (self.history.index[-1] - horizon)]
        
        if len(valid_indices) == 0:
             # Total Fallback to Monte Carlo
             print("🔮 Chronos Warning: No historical matches found. Fallback to Lite Engine.", flush=True)
             return self.generate_monte_carlo(current_features['price'], current_features['atr'], 0)
        
        print(f"🔮 Chronos Pro (Bootstrapping): Found {len(valid_indices)} historical echoes. Simulating...", flush=True)
        chosen_starts = np.random.choice(valid_indices, n_futures, replace=True)
        
        for i, idx in enumerate(chosen_starts):
            # idx is the index label, we need integer location
            try:
                # Assuming index is standard RangeIndex or effectively getting loc
                # Using direct array slicing is faster
                loc = self.history.index.get_loc(idx)
                # Get returns for next 'horizon' steps
                # Project forward from current price
                # We apply the HISTORICAL % returns to CURRENT PRICE
                hist_returns = self.history['returns'].iloc[loc+1 : loc+1+horizon].values
                
                path = [current_features['price']]
                for r in hist_returns:
                    if np.isnan(r): r = 0
                    path.append(path[-1] * (1 + r))
                
                futures[i, :] = path[1:]
            except Exception:
                futures[i, :] = current_features['price'] # Flatline fallback
                
        return futures


class ChronosArena:
    """
    Project Chronos: The Simulation Chamber.
    Tests a strategy logic against synthetic futures.
    """
    def run_simulation(self, signal_type: str, futures: np.ndarray, entry_price: float, sl_dist: float, tp_dist: float) -> dict:
        """
        Simulates the trade outcome on all futures.
        signal_type: "BUY" or "SELL"
        """
        n_paths = futures.shape[0]
        n_steps = futures.shape[1]
        
        wins = 0
        losses = 0
        scratches = 0 # Didn't hit SL or TP
        
        sl_price = entry_price - sl_dist if signal_type == "BUY" else entry_price + sl_dist
        tp_price = entry_price + tp_dist if signal_type == "BUY" else entry_price - tp_dist
        
        for i in range(n_paths):
            path = futures[i, :]
            outcome = "SCRATCH"
            
            for price in path:
                if signal_type == "BUY":
                    if price <= sl_price:
                        outcome = "LOSS"
                        break
                    elif price >= tp_price:
                        outcome = "WIN"
                        break
                else: # SELL
                    if price >= sl_price:
                        outcome = "LOSS"
                        break
                    elif price <= tp_price:
                        outcome = "WIN"
                        break
            
            if outcome == "WIN": wins += 1
            elif outcome == "LOSS": losses += 1
            else: scratches += 1
            
        win_rate = wins / n_paths if n_paths > 0 else 0
        loss_rate = losses / n_paths if n_paths > 0 else 0
        survival_rate = (wins + scratches) / n_paths
        
        return {
            "win_rate": win_rate,
            "loss_rate": loss_rate,
            "survival_rate": survival_rate,
            "n_sims": n_paths,
            "recommendation": "EXECUTE" if win_rate > 0.40 else "BLOCK"
        }
