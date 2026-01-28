import unittest
import pandas as pd
import numpy as np
from app.bif_brain import BIFBrain

class TestBIFBrain(unittest.TestCase):
    def setUp(self):
        self.brain = BIFBrain()
        
    def create_mock_df(self, trend_type="NEUTRAL", hurst=0.5):
        # Create a basic DF structure
        dates = pd.date_range(start="2024-01-01", periods=100, freq="15min")
        df = pd.DataFrame(index=dates)
        
        # We assume BIFBrain analyzes 'close' and calc hurst internally, 
        # but analyze_mtf_regime calls analyze_market_state which computes metrics.
        # However, for UNIT TESTING strictly the LOGIC in analyze_mtf_regime,
        # we can mock the internal calls or just mock the data if we trust the math.
        # But analyze_mtf_regime calls analyze_market_state on the DF.
        # It's easier to Mock 'analyze_market_state' or structural injection.
        
        # Let's create dummy DFs.
        # Note: To fully control Hurst is hard with random data.
        # We will Mock the method 'analyze_market_state' instead of generating complex time series.
        df['close'] = 100.0
        return df

    def test_scout_protocol_bullish_pullback(self):
        """Test H4 Bullish + M15 Bearish/HighHurst triggers Scout Mode."""
        
        # Mock the analyze_market_state method to return controlled stats
        original_analyze = self.brain.analyze_market_state
        
        def mock_analyze(df):
            # Identify TF by some marker? No, analyze_market_state doesn't know TF.
            # We need to control what analyze_mtf_regime receives.
            return {"hurst": 0.5, "entropy": 0.5} # Default
            
        # Instead of mocking the method which is hard contextually,
        # Let's look at analyze_mtf_regime. It iterates data_dict.
        # It calculates Trend based on Price vs EMA50 inside the function.
        # So we NEED DFs with specific Price/EMA relationships.
        
        # M15: Price < EMA (Bearish), Hurst > 0.60
        m15_df = pd.DataFrame({'close': [100]*100})
        m15_df['close'] = 90.0 # Current Price
        # EMA calculation requires history.
        # Let's just create a series where EMA end is > 90.
        # If we have 100 points of 100, EMA will be ~100.
        # Last point 90. 90 < 100 -> Bearish.
        m15_vals = [100.0] * 99 + [90.0]
        m15_df['close'] = m15_vals
        
        # H4: Bullish. Price > EMA.
        h4_vals = [100.0] * 99 + [110.0]
        h4_df = pd.DataFrame({'close': h4_vals})
        
        # H1: Irrelevant for Scout trigger but needed for completeness
        h1_df = pd.DataFrame({'close': [100.0]*100})
        
        data_dict = {'M15': m15_df, 'H1': h1_df, 'H4': h4_df}
        
        # NOW we mock analyze_market_state to return the Hurst values we want
        # We need to know which DF is being analyzed. 
        # Since we can't easily distinguish DFs inside the mock without strict identity checks,
        # we can use a side_effect based on DataFrame length or content, or just patch the return values dict?
        # analyze_mtf_regime calls:
        # results[tf] = self.analyze_market_state(df)
        
        # Let's Mock the WHOLE internal loop or just the 'results' dict construction?
        # No, let's subclass or monkeypatch.
        
        # Identity Logic:
        m15_id = id(m15_df)
        h4_id = id(h4_df)
        
        def side_effect(df):
            if id(df) == m15_id:
                return {'hurst': 0.65, 'entropy': 0.2} # High Hurst (Crash)
            elif id(df) == h4_id:
                return {'hurst': 0.55, 'entropy': 0.5} # Trending
            return {'hurst': 0.5, 'entropy': 1.0}
            
        self.brain.analyze_market_state = side_effect
        
        result = self.brain.analyze_mtf_regime(data_dict)
        
        self.assertTrue(result['scout_mode'])
        self.assertEqual(result['alignment_score'], 0.5)
        self.assertIn("MeanReverter_LONG", result['allowed_strategies'])
        self.assertNotIn("TrendHawk_LONG", result['allowed_strategies']) # Blocked
        print("Scout Bullish Pullback: PASSED")

    def test_rebel_protocol_bearish_correction(self):
        """Test M15 Range inside H4 Trend triggers Rebel/Scout Mode."""
        
        # M15: Range (Hurst < 0.45), Price irrelevant (Neutral/Bearish)
        m15_vals = [100.0] * 100
        m15_df = pd.DataFrame({'close': m15_vals})
        
        # H4: Trending (Hurst > 0.55)
        h4_vals = [100.0] * 100
        h4_df = pd.DataFrame({'close': h4_vals})
        
        data_dict = {'M15': m15_df, 'H1': m15_df, 'H4': h4_df}
        
        m15_id = id(m15_df)
        h4_id = id(h4_df)
        
        def side_effect(df):
            if id(df) == m15_id:
                return {'hurst': 0.40, 'entropy': 0.8} # Mean Reverting
            if id(df) == h4_id:
                return {'hurst': 0.60, 'entropy': 0.3} # Strong Trend
            return {'hurst': 0.5, 'entropy': 0.5}
            
        self.brain.analyze_market_state = side_effect
        
        result = self.brain.analyze_mtf_regime(data_dict)
        
        self.assertTrue(result['scout_mode']) # checking is_fighting_trend
        self.assertEqual(result['trend'], "RANGING_REBEL")
        self.assertIn("MeanReverter_SHORT", result['allowed_strategies'])
        print("Rebel Protocol: PASSED")

    def test_perfect_alignment(self):
        """Test M15/H4 Alignment."""
        m15_df = pd.DataFrame({'close': [100]*99 + [110]}) # Bullish
        h4_df = pd.DataFrame({'close': [100]*99 + [110]}) # Bullish
        
        data_dict = {'M15': m15_df, 'H1': m15_df, 'H4': h4_df}
        
        self.brain.analyze_market_state = lambda x: {'hurst': 0.6, 'entropy': 0.2}
        
        result = self.brain.analyze_mtf_regime(data_dict)
        
        self.assertEqual(result['alignment_score'], 1.0)
        self.assertFalse(result['scout_mode'])
        self.assertIn("ALL", result['allowed_strategies'])
        print("Perfect Alignment: PASSED")

if __name__ == '__main__':
    unittest.main()
