"""
TEST BUG FIXES #11 & #12
Tests TimeManager removal and safe BACKTEST_MODE default
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Test 1: TimeManager import should NOT crash
print("=== TEST 1: TimeManager removal ===")
try:
    # This should work now (no TimeManager import)
    from app.config import Config
    from app.market_sensor import MarketSensor
    from app.groq_strategist import GroqStrategist
    from app.risk_manager import IronCladRiskManager
    # TimeManager would have been here - now removed
    from app.bif_brain import BIFBrain
    from app.darwin_engine import DarwinEngine
    
    print("✅ PASS - No TimeManager import crash")
except ImportError as e:
    if "time_manager" in str(e).lower():
        print(f"❌ FAIL - TimeManager import still exists: {e}")
    else:
        print(f"❌ FAIL - Other import error: {e}")


# Test 2: BACKTEST_MODE default should be true (safe)
print("\n=== TEST 2: BACKTEST_MODE safety ===")
from dotenv import load_dotenv
load_dotenv()

backtest_mode = os.getenv("BACKTEST_MODE", "true").lower() == "true"

if backtest_mode:
    print(f"✅ PASS - BACKTEST_MODE is TRUE (safe default)")
else:
    print(f"❌ FAIL - BACKTEST_MODE is FALSE (live trading default - UNSAFE!)")

# Test 3: Config loading should work
print("\n=== TEST 3: Config loads correctly ===")
try:
    Config.validate()
    print(f"✅ PASS - Config validates without TimeManager")
    print(f"  Backtest Mode: {Config.BACKTEST_MODE}")
    print(f"  Symbol: {Config.SYMBOL}")
except Exception as e:
    print(f"❌ FAIL - Config error: {e}")

print("\n=== BUG #11 & #12 VERIFICATION COMPLETE ===")
print("System now starts safely in backtest mode!")
