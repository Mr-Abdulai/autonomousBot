import unittest
import numpy as np
import pandas as pd
from app.bif_brain import BIFBrain

class TestBIFBrain(unittest.TestCase):
    
    def setUp(self):
        self.brain = BIFBrain()

    def test_entropy_logic(self):
        # 1. Low Entropy (Ordered)
        # 100 values, all exactly 0.5. Histogram should be point mass. Entropy ~ 0.
        data_low = np.zeros(100)
        ent_low = self.brain._calculate_entropy(data_low)
        self.assertLess(ent_low, 0.1)

        # 2. High Entropy (Random Uniform)
        # 100 values, unifomly distributed -1 to 1. Entropy ~ 1.
        data_high = np.random.uniform(-1, 1, 1000)
        ent_high = self.brain._calculate_entropy(data_high)
        # It won't be exactly 1.0 due to binning issues, but should be > 0.8
        self.assertGreater(ent_high, 0.8)

    def test_hurst_logic(self):
        # 1. Random Walk (Bm). H should be close to 0.5
        np.random.seed(42)
        returns = np.random.normal(0, 0.01, 1000)
        h_random = self.brain._calculate_hurst(returns)
        # Allow some range (0.3 to 0.7) for this simple estimator
        print(f"Hurst Random: {h_random}")
        self.assertTrue(0.3 <= h_random <= 0.7)

        # 2. Strong Trend (Persistence). H > 0.5
        # We simulate a persistent series by adding positive correlation
        # Or simpler: a straight line (H=1)
        line = np.linspace(0, 10, 1000) # Perfect trend
        h_trend = self.brain._calculate_hurst(line)
        print(f"Hurst Trend: {h_trend}")
        self.assertGreater(h_trend, 0.8)

    def test_market_analysis_integration(self):
        # Mock DF
        dates = pd.date_range(start="2024-01-01", periods=200, freq="15min")
        close = np.cumprod(1 + np.random.normal(0, 0.001, 200)) # Random walk prices
        df = pd.DataFrame({"close": close}, index=dates)
        
        result = self.brain.analyze_market_state(df)
        
        self.assertIn("hurst", result)
        self.assertIn("entropy", result)
        self.assertIn("regime_id", result)
        self.assertIsInstance(result["regime_id"], int)

if __name__ == '__main__':
    unittest.main()
