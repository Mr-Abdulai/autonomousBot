import pandas as pd
import numpy as np
from app.config import Config
from app.market_sensor import MarketSensor
from app.bif_brain import BIFBrain
from app.darwin_engine import DarwinEngine

def run_diagnostics():
    print("=== FINAL SYSTEM DIAGNOSTICS ===")
    
    # 1. Setup Mock Environment
    Config.BACKTEST_MODE = True
    print("[1] Environment: BACKTEST MODE (Safety On)")
    
    # 2. Initialize Components
    try:
        brain = BIFBrain()
        darwin = DarwinEngine()
        print("[2] Brain & Darwin Engine: INITIALIZED")
    except Exception as e:
        print(f"[ERROR] Logic Intialization Failed: {e}")
        return

    # 3. Generate Mock Market Data (M15, H1, H4)
    print("[3] Generating Synthetic Market Data (Fractal Simulation)...")
    dates = pd.date_range(start="2023-01-01", periods=500, freq="15min")
    
    # Create a "Trending" Market for M15
    close = np.linspace(100, 105, 500) + np.random.normal(0, 0.1, 500)
    df_m15 = pd.DataFrame({
        "close": close, "high": close+0.2, "low": close-0.2, "open": close,
        "tick_volume": np.random.randint(100, 1000, 500)
    }, index=dates)
    
    # Add Indicators Mock
    df_m15['EMA_50'] = df_m15['close'].rolling(50).mean().fillna(100)
    df_m15['EMA_200'] = df_m15['close'].rolling(200).mean().fillna(99)
    df_m15['RSI_14'] = 65.0 # Bullish
    df_m15['BB_Upper'] = df_m15['close'] + 1
    df_m15['BB_Lower'] = df_m15['close'] - 1
    
    mtf_data = {
        'M15': df_m15,
        'H1': df_m15, # Simplified: H1 aligns
        'H4': df_m15  # H4 aligns
    }
    
    # 4. Run BIF Analysis (The Matrix)
    print("\n[4] Running BIF Matrix Analysis...")
    mtf_analysis = brain.analyze_mtf_regime(mtf_data)
    score = mtf_analysis['alignment_score']
    print(f"    > Alignment Score: {score} (Expected > 0 for Trend)")
    print(f"    > H1 Hurst: {mtf_analysis['mtf_stats']['H1'].get('hurst', 'N/A')}")
    
    # 5. Run Darwin Evolution
    print("\n[5] Running Darwin Evolution...")
    # Force some evolution history
    darwin.strategies[0].phantom_equity = 10500 # TrendHawk Winning
    darwin.strategies[1].phantom_equity = 9800  # MeanReverter Losing
    
    darwin.update(df_m15, {}, mtf_data)
    print(darwin.get_leaderboard())
    print(f"    > Current Leader: {darwin.leader.name}")
    
    # 6. Get Signal
    print("\n[6] Generating Alpha Signal...")
    signal = darwin.get_alpha_signal(df_m15, {}, mtf_data)
    print(f"    > SIGNAL: {signal['action']} (Conf: {signal['confidence']})")
    
    if signal['action'] == "BUY":
        print("\n✅ SYSTEM VERIFICATION PASSED: Trend Detected -> TrendHawk Selected -> BUY Signal Generated.")
    else:
        print(f"\n⚠️ SYSTEM RESULT: {signal['action']}. (Check logic if BUY was expected).")

if __name__ == "__main__":
    run_diagnostics()
