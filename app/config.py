import os
from dotenv import load_dotenv
import MetaTrader5 as mt5

# Load .env file
load_dotenv()

class Config:
    # Trading Settings - OPTIMIZED FOR XAUUSD (GOLD)
    SYMBOL = os.getenv("SYMBOL", "XAUUSD")  # Gold trading
    TIMEFRAME = mt5.TIMEFRAME_M15  # 15 Minute candles
    RISK_PER_TRADE = 0.01          # 1% risk per trade
    
    # GOLD-SPECIFIC: Wider stops for volatility
    STOP_LOSS_ATR_MULTIPLIER = 2.5  # Was 1.5, now 2.5 for Gold's swings
    
    # Modes
    # If BACKTEST_MODE is True, we don't send orders to MT5, just log them.
    BACKTEST_MODE = os.getenv("BACKTEST_MODE", "true").lower() == "true"
    
    # Cost Optimization - GOLD SPREADS
    SMART_FILTER = os.getenv("SMART_FILTER", "true").lower() == "true"
    MAX_OPEN_TRADES = 3 # Pyramiding Limit (keep conservative for Gold)
    AI_SCAN_INTERVAL = int(os.getenv("AI_SCAN_INTERVAL", "300")) # 5 Minutes (Seconds)
    OVERRIDE_TIME_GUARD = True # STRICTLY FOR DEBUGGING/TESTING. Ignore Market Hours.
    
    # Execution Aggressiveness - GOLD OPTIMIZED
    # 0.7 = Slightly aggressive (Gold moves fast, need to catch momentum)
    EXECUTION_MODE = float(os.getenv("EXECUTION_MODE", "0.7"))  # Was 0.6, now 0.7 for Gold
    
    # GOLD-SPECIFIC: Spread tolerance
    MAX_SPREAD_PIPS = 5.0  # Gold can have 2-5 pip spreads
    MAX_SPREAD_POINTS = 500  # 500 points for Exness (3-digit) = 5.0 pips (vs 50 for 2-digit)
    
    # Phase 68: Dynamic Risk
    ENABLE_DYNAMIC_RISK = True # Scales risk based on PnL
    MAX_DAILY_LOSS = 0.05 # 5% Max Daily Loss (Circuit Breaker)
    
    # Credentials
    MT5_LOGIN = os.getenv("MT5_LOGIN")
    MT5_PASSWORD = os.getenv("MT5_PASSWORD")
    MT5_SERVER = os.getenv("MT5_SERVER")
    GROQ_API_KEY = os.getenv("GROQ_API_KEY")

    # Project Paths
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    TRADES_FILE = os.path.join(BASE_DIR, "trades.json")

    @staticmethod
    def validate():
        """Checks if critical environment variables are set."""
        missing = []
        if not Config.GROQ_API_KEY:
            missing.append("GROQ_API_KEY")
        if not Config.MT5_LOGIN:
            missing.append("MT5_LOGIN")
        if not Config.MT5_PASSWORD:
            missing.append("MT5_PASSWORD")
        if not Config.MT5_SERVER:
            missing.append("MT5_SERVER")
        
        if missing:
            raise EnvironmentError(f"Missing critical environment variables: {', '.join(missing)}. Please check your .env file.")
        
        # Validate data types for MT5 login
        try:
            int(Config.MT5_LOGIN)
        except (ValueError, TypeError):
             raise EnvironmentError("MT5_LOGIN must be an integer.")

        print(f"Configuration loaded. Backtest Mode: {Config.BACKTEST_MODE}")
