import sys
import pandas as pd
from app.darwin_engine import DarwinEngine

print("DEBUG: Initializing DarwinEngine...")
try:
    engine = DarwinEngine()
    print(f"SUCCESS: Engine initialized with {len(engine.strategies)} strategies.")
    
    # Check for RSI Matrix
    rsi = next((s for s in engine.strategies if "RSI_Matrix" in s.name), None)
    if rsi:
        print(f"FOUND: {rsi.name}")
    else:
        print("ERROR: RSI_Matrix not found in strategies.")
        
    # Check for MACD
    macd = next((s for s in engine.strategies if "MACD_Cross" in s.name), None)
    if macd:
        print(f"FOUND: {macd.name}")
    else:
        print("ERROR: MACD_Cross not found in strategies.")

    # Run the Failing Test Logic Manually
    print("\nRunning Test Case 1: Smart Scoring...")
    
    # Helper to find strat by partial name
    def get_strat(subname):
        return next(s for s in engine.strategies if subname in s.name)

    th = get_strat("TrendHawk_LONG_21p")
    th.phantom_equity = 15000 
    th.peak_equity = 20000 
    th.max_drawdown = 0.25 
    
    mr = get_strat("MeanRev_LONG_2.0SD")
    mr.phantom_equity = 12000 
    mr.peak_equity = 12000
    mr.max_drawdown = 0.0 
    
    df = pd.DataFrame({
        'close': [100], 'high': [101], 'low': [99], 'open': [100]
    })
    
    # Mock Indicators
    indicators = {
        'ema_50': 100,
        'EMA_50': 100,
        'RSI_14': 50,
        'bb_upper': 102,
        'bb_lower': 98
    }
    
    engine.update(df, indicators, {})
    
    print(f"Leader is: {engine.leader.name}")
    if engine.leader.name == "MeanRev_LONG_2.0SD":
        print("TEST PASSED: Stable Strategy Won.")
    else:
        print(f"TEST FAILED: {engine.leader.name} Won.")

except Exception as e:
    print(f"CRITICAL ERROR: {e}")
    import traceback
    traceback.print_exc()
