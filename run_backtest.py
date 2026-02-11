from app.backtest_engine import Backtester
from app.config import Config
import sys

def main():
    print("=== 🕰️  SENTIENT TRADER TIME MACHINE (Backtester) ===")
    
    # 1. Setup
    symbol = input(f"Enter Symbol [{Config.SYMBOL}]: ") or Config.SYMBOL
    days = input("Enter Days to simulate [30]: ") or "30"
    balance = input("Enter Starting Balance [10000]: ") or "10000"
    leverage = input("Enter Leverage [500]: ") or "500"
    
    try:
        days = int(days)
        balance = float(balance)
        leverage = int(leverage)
    except:
        print("Invalid input. Using defaults.")
        days = 30
        balance = 10000.0
        leverage = 500
        
    print(f"\nInitializing Backtest for {symbol} ({days} days, ${balance:.0f}, 1:{leverage})...")
    
    # 2. Init Engine
    engine = Backtester(symbol=symbol, initial_capital=balance, leverage=leverage)
    
    # 3. Run
    try:
        engine.run(days=days)
    except KeyboardInterrupt:
        print("\n🛑 Simulation Aborted by User.")
    except Exception as e:
        print(f"\n❌ CRITICAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        
    print("\nDone.")

if __name__ == "__main__":
    main()
