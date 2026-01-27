import unittest
import pandas as pd
import numpy as np
from app.ta_lib import TALib
from app.market_sensor import MarketSensor

class TestFractalEngine(unittest.TestCase):
    def setUp(self):
        self.sensor = MarketSensor()

    def test_fractal_identification(self):
        """Test if Bill Williams Fractals are correctly identified (5-bar pattern)."""
        # Create a synthetic UP Fractal: Low, Mid, High, Mid, Low
        # Index: 0, 1, 2(Top), 3, 4
        # Fractal is confirmed at index 2 after index 4 closes.
        
        data = {
            'open':  [10, 11, 12, 11, 10, 10, 10], # Extra bars for shifting
            'high':  [10, 12, 15, 12, 10, 10, 9],  # Index 2 (15) is > Index 0,1 and 3,4
            'low':   [8,  9,  10, 9,  8,  8,  8],
            'close': [10, 11, 12, 11, 10, 10, 9],
            'tick_volume': [100]*7
        }
        df = pd.DataFrame(data)
        
        df_fractals = TALib.identify_fractals(df)
        
        # Check Bar 2 (Index 2)
        # It should be a Fractal High
        self.assertTrue(df_fractals.iloc[2]['fractal_high'], "Index 2 should be an Up Fractal")
        
        # Check Bar 1 or 3 -> Should NOT be fractals
        self.assertFalse(df_fractals.iloc[1]['fractal_high'], "Index 1 should not be Up Fractal")
        self.assertFalse(df_fractals.iloc[3]['fractal_high'], "Index 3 should not be Up Fractal")

    def test_fractal_breakout(self):
        """Test if MarketSensor correctly detects a Break of the Fractal Level."""
        # 1. Setup a Past Fractal High at 15.0
        # 2. Have price break it at the end.
        
        data = {
            'high':  [10, 12, 15, 12, 10, 14, 16], # Index 2 is Fractal (15). Index 6 breaks it (16).
            'low':   [8,  9,  10, 9,  8,  8,  8],
            'close': [10, 11, 12, 11, 10, 14, 15.5], # Non-final close > 15? No. Final close 15.5 > 15.
            'open':  [10, 10, 10, 10, 10, 10, 10], # dummy
            'tick_volume': [100]*7
        }
        df = pd.DataFrame(data)
        
        # Run detection
        signal, level = self.sensor.get_fractal_structure(df)
        
        self.assertEqual(signal, "BREAK_UP", "Should detect Breakout of Up Fractal")
        self.assertEqual(level, 15.0, "Breakout Level should be the Fractal High (15.0)")
        
    def test_fractal_no_break(self):
        """Test no signal if price is below fractal."""
        data = {
            'high':  [10, 12, 15, 12, 10, 14, 14.5], # Index 6 (14.5) < 15
            'low':   [8,  9,  10, 9,  8,  8,  8],
            'close': [10, 11, 12, 11, 10, 14, 14.0],
            'open':  [10, 10, 10, 10, 10, 10, 10],
            'tick_volume': [100]*7
        }
        df = pd.DataFrame(data)
        
        signal, level = self.sensor.get_fractal_structure(df)
        self.assertEqual(signal, "NONE", "Should be NO signal if price didn't break")

if __name__ == '__main__':
    unittest.main()
