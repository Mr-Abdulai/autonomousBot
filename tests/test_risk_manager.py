import unittest
import sys
from unittest.mock import MagicMock

# 1. Mock critical dependencies
sys.modules["MetaTrader5"] = MagicMock()

# 2. Imports
try:
    from app.config import Config
    from app.risk_manager import IronCladRiskManager, EquityCurveManager
except ImportError as e:
    print(f"IMPORT ERROR: {e}")
    raise

class TestEquityCurve(unittest.TestCase):
    
    def setUp(self):
        print("SETTING UP TEST...")
        # Reset Config
        Config.RISK_PER_TRADE = 0.01
        Config.MAX_DAILY_LOSS = 0.05
        Config.ENABLE_DYNAMIC_RISK = True
        
        self.rm = IronCladRiskManager()
        self.rm.update_account_state(10000.0, is_new_day=True)
        print("SETUP DONE")

    def test_standard_risk(self):
        print("TEST: Standard Risk")
        factor = self.rm.equity_manager.get_risk_scale_factor()
        self.assertEqual(factor, 1.5) 

    def test_drawdown_scaling_defensive(self):
        print("TEST: Defensive Risk")
        self.rm.update_account_state(9400.0) 
        factor = self.rm.equity_manager.get_risk_scale_factor()
        self.assertEqual(factor, 0.5)
        
    def test_drawdown_scaling_survival(self):
        print("TEST: Survival Risk")
        self.rm.update_account_state(8000.0) 
        factor = self.rm.equity_manager.get_risk_scale_factor()
        self.assertEqual(factor, 0.25)

    def test_daily_loss_circuit_breaker(self):
        print("TEST: Circuit Breaker")
        self.rm.update_account_state(10000.0, is_new_day=True)
        self.rm.update_account_state(9400.0)
        is_broken = self.rm.equity_manager.check_circuit_breaker()
        self.assertTrue(is_broken)
        
        res = self.rm.validate_signal({"action": "BUY", "confidence_score": 0.9})
        self.assertEqual(res['action'], "HOLD")
        self.assertIn("DAILY LOSS", res['reasoning_summary'])

    def test_position_sizing_calc(self):
        print("TEST: Position Sizing")
        size = self.rm.calculate_position_size(10000.0, 1.0000, 0.9900)
        self.assertAlmostEqual(size, 15000.0)

if __name__ == '__main__':
    unittest.main()
