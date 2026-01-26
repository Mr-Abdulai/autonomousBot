
import unittest
import sys
from unittest.mock import MagicMock

# Mock MT5 before importing market sensor
sys.modules['MetaTrader5'] = MagicMock()

import pandas as pd
from app.market_sensor import MarketSensor

class TestPatterns(unittest.TestCase):
    def setUp(self):
        self.sensor = MarketSensor()
        # Mock initialize explicitly just in case
        self.sensor.initialize = MagicMock(return_value=True)

    def test_bullish_engulfing(self):
        # Prev: Red Candle (Open 10, Close 8)
        # Curr: Green Candle (Open 7, Close 11) - Engulfs
        data = {
            'open':  [10.0, 7.0],
            'high':  [10.5, 11.5],
            'low':   [7.5, 6.5],
            'close': [8.0, 11.0]
        }
        df = pd.DataFrame(data)
        patterns = self.sensor.detect_patterns(df)
        self.assertIn("BULLISH_ENGULFING", patterns)

    def test_bearish_engulfing(self):
        # Prev: Green Candle (Open 8, Close 10)
        # Curr: Red Candle (Open 11, Close 7) - Engulfs
        # Body 1: 2. Body 2: 4.
        data = {
            'open':  [8.0, 11.0],
            'high':  [10.5, 11.5],
            'low':   [7.5, 6.5],
            'close': [10.0, 7.0]
        }
        df = pd.DataFrame(data)
        patterns = self.sensor.detect_patterns(df)
        self.assertIn("BEARISH_ENGULFING", patterns)

    def test_bullish_pinbar(self):
        # Hammer: Small Body at top, Long Lower Wick
        # Open 10, Close 10.5 (Body 0.5)
        # Low 5.0 (Lower Wick 5.0) -> 10x Body (Strong Hammer)
        data = {
            'open':  [10.0, 10.0],
            'high':  [10.5, 10.6],
            'low':   [9.0, 5.0],
            'close': [9.5, 10.5]
        }
        df = pd.DataFrame(data)
        patterns = self.sensor.detect_patterns(df)
        self.assertIn("BULLISH_PINBAR", patterns)

    def test_bearish_pinbar(self):
        # Shooting Star: Small Body at bottom, Long Upper Wick
        # Open 10, Close 10.5 (Body 0.5)
        # High 15.0 (Upper Wick 4.5) -> 9x Body
        data = {
            'open':  [10.0, 10.0],
            'high':  [10.5, 15.0],
            'low':   [9.0, 9.9],
            'close': [9.5, 10.5]
        }
        df = pd.DataFrame(data)
        patterns = self.sensor.detect_patterns(df)
        self.assertIn("BEARISH_PINBAR", patterns)

if __name__ == '__main__':
    unittest.main()
