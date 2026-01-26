import sys
import os

def check_imports():
    print("Checking Imports...")
    try:
        import MetaTrader5
        import pandas
        import groq
        import dotenv
        print("[OK] All libraries installed.")
    except ImportError as e:
        print(f"[FAIL] Missing library: {e}")
        return False
    return True

def check_config():
    print("Checking Config...")
    try:
        from app.config import Config
        try:
            Config.validate()
        except EnvironmentError as e:
            print(f"[WARN] Config Validation Failed: {e}")
            print("This is expected if you haven't edited .env yet.")
            return True # Not a code failure, just config missing
        print("[OK] Config handling works.")
    except Exception as e:
        print(f"[FAIL] Config module error: {e}")
        return False
    return True

def check_modules():
    print("Checking Modules...")
    try:
        from app.market_sensor import MarketSensor
        from app.groq_strategist import GroqStrategist
        from app.risk_manager import IronCladRiskManager
        from app.execution_engine import ExecutionEngine
        
        s = MarketSensor()
        g = GroqStrategist()
        r = IronCladRiskManager()
        e = ExecutionEngine()
        print("[OK] All modules instantiated successfully.")
    except Exception as e:
        print(f"[FAIL] Module instantiation error: {e}")
        return False
    return True

if __name__ == "__main__":
    print("=== System Verification ===")
    if check_imports() and check_config() and check_modules():
        print("\n[SUCCESS] System structure is valid.")
        print("NEXT STEPS:")
        print("1. Edit .env with your keys.")
        print("2. Ensure MT5 is running.")
        print("3. Run 'python main.py'")
    else:
        print("\n[FAIL] Issues detected.")
