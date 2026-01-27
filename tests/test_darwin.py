import unittest
import pandas as pd
import numpy as np
from app.darwin_engine import DarwinEngine, TrendHawk, MeanReverter, ShadowStrategy

class TestDarwinEngine(unittest.TestCase):
    def setUp(self):
        self.engine = DarwinEngine()
        
    def create_mock_df(self):
        dates = pd.date_range(start="2023-01-01", periods=100, freq="15min")
        close = np.linspace(100, 110, 100) # Uptrend
        df = pd.DataFrame({
            "close": close, 
            "high": close + 0.5, 
            "low": close - 0.5,
            "EMA_50": close - 1, # Below price
            "EMA_200": close - 2,
            "RSI_14": np.full(100, 60),
            "BB_Upper": close + 1,
            "BB_Lower": close - 1,
            "ADX": np.full(100, 30)
        }, index=dates)
        return df

    def test_shadow_accounting(self):
        strat = TrendHawk("TestHawk")
        # Start: 10000
        strat.active_trade = {'entry': 100.0, 'type': 'BUY', 'sl': 99.0, 'tp': 102.0}
        
        # 1. Update with price 100.5 (Open)
        strat.update_performance(100.5)
        self.assertEqual(strat.phantom_equity, 10000.0)
        self.assertIsNotNone(strat.active_trade)
        
        # 2. Update with price 102.5 (TP Hit)
        strat.update_performance(102.5)
        # Profit = 2.0. Scale * 1000 = 2000. Equity = 12000.
        self.assertEqual(strat.phantom_equity, 12000.0)
        self.assertIsNone(strat.active_trade)
        
    def test_leader_selection(self):
        # Helper to set equity by name
        def set_equity(name, val):
            for s in self.engine.strategies:
                if s.name == name:
                    s.phantom_equity = val
                    return
        
        # Scenario 1: TrendHawk Wins
        set_equity("TrendHawk", 15000)
        set_equity("MeanReverter", 9000)
        set_equity("Sniper", 10000)
        
        # Trigger update (requires data)
        df = self.create_mock_df()
        self.engine.update(df, {}, {})
        
        self.assertEqual(self.engine.leader.name, "TrendHawk")
        
        # Scenario 2: MeanReverter Wins
        set_equity("TrendHawk", 5000)
        set_equity("MeanReverter", 20000)
        set_equity("Sniper", 10000)
        
        self.engine.update(df, {}, {})
        self.assertEqual(self.engine.leader.name, "MeanReverter")

if __name__ == '__main__':
    unittest.main()
