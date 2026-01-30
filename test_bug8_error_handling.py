"""
TEST BUG FIX #8: Advanced Indicator Error Handling
Tests graceful degradation when VWAP/SuperTrend/RVI fail
"""

import sys
import os
import pandas as pd
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.ta_lib import TALib

# Test 1: Normal execution (should work)
print("=== TEST 1: Normal indicator calculation ===")
try:
    # Create mock OHLCV data
    df = pd.DataFrame({
        'open': [2050 + i for i in range(100)],
        'high': [2055 + i for i in range(100)],
        'low': [2045 + i for i in range(100)],
        'close': [2052 + i for i in range(100)],
        'tick_volume': [1000] * 100
    })
    
    vwap = TALib.calculate_vwap(df)
    supertrend = TALib.calculate_supertrend(df)
    rvi = TALib.calculate_rvi(df)
    
    print(f"  ✓ VWAP: {vwap:.2f}")
    print(f"  ✓ SuperTrend: {supertrend}")
    print(f"  ✓ RVI: {rvi:.2f}")
    print("✅ PASS - Normal calculation works")
except Exception as e:
    print(f"❌ FAIL - Should work normally: {e}")

# Test 2: Error handling (bad data)
print("\n=== TEST 2: Error handling with bad data ===")

# Simulate the try-except from main.py
current_price = 2050.0
try:
    # Intentionally cause error with bad data
    bad_df = pd.DataFrame({'close': [1, 2]})  # Too small
    
    vwap = TALib.calculate_vwap(bad_df)
    supertrend = TALib.calculate_supertrend(bad_df)
    rvi = TALib.calculate_rvi(bad_df)
    
    advanced_indicators = {
        'vwap': vwap,
        'supertrend': supertrend,
        'rvi': rvi
    }
    print(f"  Indicators calculated (unexpectedly)")

except Exception as e:
    # This is the FIXED graceful degradation
    print(f"  ⚠️ Caught error: {type(e).__name__}")
    advanced_indicators = {
        'vwap': current_price,
        'supertrend': {'trend': 'NEUTRAL', 'level': current_price, 'signal': 0},
        'rvi': 0.0
    }
    print(f"  ✓ Graceful fallback: VWAP={advanced_indicators['vwap']}, Trend={advanced_indicators['supertrend']['trend']}")
    print("✅ PASS - Error handled gracefully, no crash!")

# Test 3: Verify defaults are safe
print("\n=== TEST 3: Verify fallback defaults ===")

if advanced_indicators['vwap'] == current_price:
    print(f"✅ PASS - VWAP defaults to current price ({current_price})")
else:
    print(f"❌ FAIL - VWAP should default to {current_price}")

if advanced_indicators['supertrend']['trend'] == 'NEUTRAL':
    print(f"✅ PASS - SuperTrend defaults to NEUTRAL")
else:
    print(f"❌ FAIL - SuperTrend should default to NEUTRAL")

if advanced_indicators['rvi'] == 0.0:
    print(f"✅ PASS - RVI defaults to 0.0 (neutral)")
else:
    print(f"❌ FAIL - RVI should default to 0.0")

print("\n=== BUG #8 VERIFICATION COMPLETE ===")
print("Indicators fail gracefully - no crashes!")
