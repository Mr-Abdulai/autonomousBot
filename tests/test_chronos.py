import unittest
import pandas as pd
import numpy as np
from app.chronos import ChronosWeaver, ChronosArena

class TestChronosEngine(unittest.TestCase):
    def setUp(self):
        # Create Dummy History
        dates = pd.date_range(start='2023-01-01', periods=1000, freq='15min')
        self.history = pd.DataFrame({
            'time': dates,
            'close': np.random.normal(100, 1, 1000).cumsum() + 1000 # Random Walk
        })
        self.history['tick_volume'] = 100
        
        self.weaver = ChronosWeaver(self.history)
        self.arena = ChronosArena()
        
    def test_monte_carlo_lite(self):
        """Test Lite Engine (Monte Carlo) Generation"""
        current_price = 100.0
        atr = 1.0 # 1% vol
        drift = 0.0
        
        futures = self.weaver.generate_monte_carlo(current_price, atr, drift, n_futures=100, horizon=10)
        
        self.assertEqual(futures.shape, (100, 10))
        # Start of path should be close to current price
        # Note: generated path excludes S0, so first point is S1
        self.assertTrue(90 < futures[0,0] < 110)
        
    def test_historical_echoes_pro(self):
        """Test Pro Engine (Historical Echoes) Generation"""
        features = {
            'price': 100.0, 
            'atr': 1.0, 
            'volatility': 0.01
        }
        
        # Should work even with random data (might default to fallback or find random matches)
        futures = self.weaver.generate_historical_echoes(features, n_futures=50, horizon=20)
        
        self.assertEqual(futures.shape, (50, 20))
        
    def test_simulation_arena(self):
        """Test Arena Logic (Win Rate)"""
        # Create specific futures to test Win/Loss
        # 3 paths: Win, Loss, Scratch
        futures = np.array([
            [101, 102, 103, 104, 105], # Goes UP to 105
            [99, 98, 97, 96, 95],      # Goes DOWN to 95
            [100, 101, 100, 101, 100]  # Wiggles
        ])
        
        # Strategy: BUY. Entry: 100. SL: 96 (dist 4). TP: 104 (dist 4).
        # Path 0: Hits 104 -> WIN
        # Path 1: Hits 96 -> LOSS (Wait, 96 is hit at index 3)
        # Path 2: Scratch
        
        res = self.arena.run_simulation("BUY", futures, 100, sl_dist=4, tp_dist=4)
        
        self.assertEqual(res['n_sims'], 3)
        self.assertAlmostEqual(res['win_rate'], 1/3)
        self.assertAlmostEqual(res['loss_rate'], 1/3) # Hitting SL exactly counts as LOSS? <= Logic says yes.
        # Check Path 1: 99, 98, 97, 96. <= 96 triggers LOSS.
        
    def test_veto_logic(self):
        """Test Block/Confirm Logic"""
        # If Win Rate < 0.4 -> BLOCK
        futures = np.zeros((10, 10)) + 90 # All crash
        res = self.arena.run_simulation("BUY", futures, 100, 5, 5)
        self.assertEqual(res['recommendation'], "BLOCK")
        
        futures = np.zeros((10, 10)) + 110 # All moon
        res = self.arena.run_simulation("BUY", futures, 100, 5, 5)
        self.assertEqual(res['recommendation'], "EXECUTE")

if __name__ == '__main__':
    unittest.main()
