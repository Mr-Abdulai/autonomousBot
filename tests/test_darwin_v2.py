import unittest
import pandas as pd
from app.darwin_engine import DarwinEngine, TrendHawk, MeanReverter

class TestDarwinSmartScoring(unittest.TestCase):
    def setUp(self):
        self.engine = DarwinEngine()
        
        # Helper to find strat by partial name
        def get_strat(subname):
            return next(s for s in self.engine.strategies if subname in s.name)

        # Strategy 1: TrendHawk_LONG_20p (High Returns, MASSIVE Drawdown)
        th = get_strat("TrendHawk_LONG_20p")
        th.phantom_equity = 15000 # +50%
        th.peak_equity = 20000 
        th.max_drawdown = 0.25 # 25% DD from Peak
        
        # Strategy 2: MeanRev_LONG_Std (Lower Returns, Zero Drawdown)
        mr = get_strat("MeanRev_LONG_Std")
        mr.phantom_equity = 12000 # +20%
        mr.peak_equity = 12000
        mr.max_drawdown = 0.0 # 0% DD
        
        # Mock full OHLC for TrendHawk
        df = pd.DataFrame({
            'close': [100], 'high': [101], 'low': [99], 'open': [100]
        })
        self.engine.update(df, {}, {}) # Trigger sort
        
        self.assertEqual(self.engine.leader.name, "MeanRev_LONG_Std", "Stable strategy should beat Volatile one")

    def test_regime_boost(self):
        """Verify that Regime boosts the correct strategy."""
        # Helper to find strat by partial name
        def get_strat(subname):
            return next(s for s in self.engine.strategies if subname in s.name)
            
        th = get_strat("TrendHawk_LONG_20p")
        mr = get_strat("MeanRev_LONG_Std")
        th.phantom_equity = 10000
        mr.phantom_equity = 10000
        
        # 1. Regime = TREND (Hurst > 0.55)
        # Should boost TrendHawk by 1.2x
        mtf_data = {
            'analysis': {
                'M15': {'hurst': 0.70} # Strong Trend
            }
        }
        
        df = pd.DataFrame({'close': [100], 'high': [101], 'low': [99], 'open': [100]})
        self.engine.update(df, {}, mtf_data)
        
        self.assertIn("TrendHawk", self.engine.leader.name, "Trend regime should favor TrendHawk")
        
        # 2. Regime = CHOP (Hurst < 0.45)
        mtf_data['analysis']['M15']['hurst'] = 0.30
        self.engine.update(df, {}, mtf_data)
        self.assertIn("MeanRev", self.engine.leader.name, "Chop regime should favor MeanReverter")
        
    def test_directional_filter(self):
        """Verify that LONG-only strategies ignore SELL signals."""
        def get_strat(subname):
            return next(s for s in self.engine.strategies if subname in s.name)
            
        th_long = get_strat("TrendHawk_LONG_20p")
        
        # Create a Bearish Breakout scenario
        # Price 90, Low_20 = 95. Breakout DOWN.
        # Should generate SELL raw, but be filtered to HOLD.
        dates = pd.date_range("2023-01-01", periods=30, freq="15min")
        df = pd.DataFrame({
             'close': [150]*29 + [90], 
             'high': [155]*30,
             'low': [95]*29 + [90],
             'open': [100]*30
        }, index=dates)
        
        indicators = {'EMA_50': 120} # Price < EMA -> Bearish
        
        # Raw check (if we could access private method, but we test public)
        sig = th_long.generate_signal(df, indicators, {})
        
        self.assertEqual(sig['action'], "HOLD", "LONG-only strategy must HOLD on Bear signal")

if __name__ == '__main__':
    unittest.main()
