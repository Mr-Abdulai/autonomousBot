import sys
from unittest.mock import MagicMock

# MOCK MT5 BEFORE IMPORTING CONFIG
sys.modules["MetaTrader5"] = MagicMock()

try:
    from app.risk_manager import IronCladRiskManager
    print("IMPORT SUCCESS")
except Exception as e:
    print(f"IMPORT FAILED: {e}")
    import traceback
    traceback.print_exc()
