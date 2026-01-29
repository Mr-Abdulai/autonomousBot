import unittest
import pandas as pd
from app.darwin_engine import DarwinEngine, TrendHawk, MeanReverter

class TestDarwinSmartScoring(unittest.TestCase):
    def setUp(self):
        self.engine = DarwinEngine()
        
        # Helper to find strat by partial name
        def get_strat(subname):
            return next(s for s in self.engine.strategies if subname in s.name)

        # Strategy 1: TrendHawk_LONG_21p 
        th = get_strat("TrendHawk_LONG_21p")
        th.phantom_equity = 15000 # +50%
        th.peak_equity = 20000 
        th.max_drawdown = 0.25 # 25% DD from Peak
        
        # Strategy 2: MeanRev_LONG_2.0SD (Lower Returns, Zero Drawdown)
        mr = get_strat("MeanRev_LONG_2.0SD")
        mr.phantom_equity = 12000 # +20%
        mr.peak_equity = 12000
        mr.max_drawdown = 0.0 # 0% DD
        
        # Mock full OHLC for TrendHawk
        df = pd.DataFrame({
            'close': [100], 'high': [101], 'low': [99], 'open': [100]
        })
        self.engine.update(df, {}, {}) # Trigger sort
        
        self.assertEqual(self.engine.leader.name, "MeanRev_LONG_2.0SD", "Stable strategy should beat Volatile one")

    def test_regime_boost(self):
        """Verify that Regime boosts the correct strategy."""
        # Helper to find strat by partial name
        def get_strat(subname):
            return next(s for s in self.engine.strategies if subname in s.name)
            
        th = get_strat("TrendHawk_LONG_21p")
        mr = get_strat("MeanRev_LONG_2.0SD")
        th.phantom_equity = 10000
        mr.phantom_equity = 10000
        
        # 1. Regime = TREND (Hurst > 0.55)
        # Should boost TrendHawk by 1.2x
        mtf_data = {
            'analysis': {
                'M15': {'hurst': 0.70}, # Strong Trend
                'trend': 'BULLISH' # Explicit Trend Direction needed for Hydra boost
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
            
        th_long = get_strat("TrendHawk_LONG_21p")
        
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

    def test_consensus_voting(self):
        """Verify Consensus Logic (Unanimous vs Conflict)."""
        # Mock Strategies by modifying phantom equity to force top ranking
        s1 = self.engine.strategies[0]
        s2 = self.engine.strategies[1]
        s3 = self.engine.strategies[2]
        
        s1.phantom_equity = 20000 
        s2.phantom_equity = 19000
        s3.phantom_equity = 18000
        
        # We need to Mock generate_signal logic for these SPECIFIC instances.
        # Python's `unittest.mock` is great but here we can just monkey-patch the instance method 
        # OR just supply data that triggers them all.
        # But they are different strategies (TrendHawk, MeanRev etc), hard to align input data for all.
        # Monkey Patching `generate_signal` on the instances is safer for unit logic check.
        
        s1.generate_signal = lambda d, i, m: {'action': 'BUY'}
        s2.generate_signal = lambda d, i, m: {'action': 'BUY'}
        s3.generate_signal = lambda d, i, m: {'action': 'BUY'}
        
        # 1. Unanimous BUY
        res = self.engine.get_consensus_signal(None, None, {})
        self.assertEqual(res['action'], 'BUY')
        self.assertEqual(res['confidence'], 1.0)
        self.assertIn("UNANIMOUS", res['reason'])
        
        # 2. Majority BUY (2 Buy, 1 Sell)
        s3.generate_signal = lambda d, i, m: {'action': 'SELL'}
        res = self.engine.get_consensus_signal(None, None, {})
        self.assertEqual(res['action'], 'BUY')
        self.assertEqual(res['confidence'], 0.8)
        self.assertIn("MAJORITY", res['reason'])
        
        # 3. Conflict (1 Buy, 2 Sell) -> Top 3 Logic: 2 Sell wins Majority logic.
        s1.generate_signal = lambda d, i, m: {'action': 'BUY'} # Leader says BUY
        s2.generate_signal = lambda d, i, m: {'action': 'SELL'}
        s3.generate_signal = lambda d, i, m: {'action': 'SELL'}
        
        res = self.engine.get_consensus_signal(None, None, {})
        self.assertEqual(res['action'], 'SELL') # Should follow Majority
        self.assertEqual(res['confidence'], 0.8)
        
        # 4. Hung Jury (1 Buy, 1 Sell, 1 Hold)
        s1.generate_signal = lambda d, i, m: {'action': 'BUY'}
        s2.generate_signal = lambda d, i, m: {'action': 'SELL'}
        s3.generate_signal = lambda d, i, m: {'action': 'HOLD'}
        
        res = self.engine.get_consensus_signal(None, None, {})
        self.assertEqual(res['action'], 'HOLD')
        self.assertIn("HUNG JURY", res['reason'])

if __name__ == '__main__':
    unittest.main()
