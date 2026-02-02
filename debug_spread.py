
import MetaTrader5 as mt5
import time
from app.config import Config

def diagnose():
    if not mt5.initialize():
        print("MT5 Init Failed")
        return

    symbol = Config.SYMBOL
    if not mt5.symbol_select(symbol, True):
        print(f"Failed to select {symbol}")
        return

    info = mt5.symbol_info(symbol)
    if not info:
        print("No symbol info")
        return

    print(f"=== DIAGNOSIS FOR {symbol} ===")
    print(f"Digits: {info.digits}")
    print(f"Point: {info.point:.8f}")
    print(f"Spread (Points): {info.spread}")
    print(f"Contract Size: {info.trade_contract_size}")
    
    # Calculate Pip Value assumption
    # Usual convention: 
    # Forex 5 digits: 1 pip = 0.0001 (10 points)
    # Gold 2 digits: 1 pip = 0.10 or 0.01? 
    # Usually XAUUSD 1 Pip = $0.10 price change.
    
    # If Digits=2 (2000.01): Point=0.01. 1 Pip ($0.10) = 10 Points.
    # If Digits=3 (2000.001): Point=0.001. 1 Pip ($0.10) = 100 Points.
    
    print(f"Current Spread Value: {info.spread * info.point:.4f}")
    
    print("=== CONFIG CHECK ===")
    print(f"Config.MAX_SPREAD_POINTS: {Config.MAX_SPREAD_POINTS}")
    print(f"Config.MAX_SPREAD_PIPS: {Config.MAX_SPREAD_PIPS}")
    
    if info.spread > Config.MAX_SPREAD_POINTS:
        print(f"❌ BLOCKING ISSUE: Spread {info.spread} > Config {Config.MAX_SPREAD_POINTS}")
        print("Recommendation: Increase MAX_SPREAD_POINTS or implement dynamic pipette handling.")
    else:
        print("✅ Spread is within limits.")

    mt5.shutdown()

if __name__ == "__main__":
    diagnose()
