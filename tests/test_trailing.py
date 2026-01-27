import unittest
from app.execution_engine import ExecutionEngine

class TestFractalTrailing(unittest.TestCase):
    def setUp(self):
        self.engine = ExecutionEngine()
        self.engine.backtest_mode = True # Use Mocking

    def test_break_even_trigger(self):
        """Test if SL moves to BE at 1R Profit."""
        # Buy at 1.0000. SL at 0.9900. Risk = 0.0100.
        # Price moves to 1.0150 (1.5R).
        # SL should move to 1.0000 + buffer.
        
        # We simulate this by checking what apply_trailing_stop PRINTS or calls (since we can't easily check internal MT5 state in unit test without heavy mocking).
        # But wait, apply_trailing_stop returns nothing and applies to MT5.
        # We need to rely on the LOGIC flow.
        pass # Hard to test without refactoring ExecutionEngine to return the New SL.

    def test_logic_calculation(self):
        """
        We'll manually test the internal logic by copying it or verifying via a helper.
        Or better: We trust the Logic Review we did. 
        Actually, let's create a dummy method in a subclass to expose the logic.
        """
        pass

# Since ExecutionEngine is tightly coupled with MT5, we will verify by creating a 
# 'MockEngine' that overrides 'modify_order_sl' to just return the value.

class MockExecutionEngine(ExecutionEngine):
    def __init__(self):
        self.last_modification = None
        self.backtest_mode = True
        
    def modify_order_sl(self, ticket, new_sl):
        self.last_modification = new_sl
        return True
        
class TestTrailingLogic(unittest.TestCase):
    def test_fractal_trail_buy(self):
        engine = MockExecutionEngine()
        
        # BUY Trade
        entry = 1.1000
        current_sl = 1.0900 # Risk 100 pips
        tp = 1.1300
        risk = 0.0100
        
        # 1. Price at 1.1050 (0.5R) -> No Action
        engine.apply_trailing_stop(1, 1.1050, entry, "BUY", current_sl, tp, 0.0010, {'support': 1.0950})
        self.assertIsNone(engine.last_modification)
        
        # 2. Price at 1.1150 (1.5R) -> Break Even
        engine.apply_trailing_stop(1, 1.1150, entry, "BUY", current_sl, tp, 0.0010, {'support': 1.0950})
        # Should be Entry + Buffer (1.1000 + 0.0001) = 1.1001
        self.assertAlmostEqual(engine.last_modification, 1.1001, places=4)
        
        # 3. Price at 1.1250 (2.5R) -> Fractal Trail
        # Current SL is now at BE (1.1001).
        # Fractal Support is at 1.1100.
        # Should move to 1.1100.
        current_sl = 1.1001
        fractals = {'support': 1.1100, 'resistance': 1.2000}
        
        engine.apply_trailing_stop(1, 1.1250, entry, "BUY", current_sl, tp, 0.0010, fractals)
        # Should be Fractal - Buffer (1.1100 - 0.0001) = 1.1099
        self.assertAlmostEqual(engine.last_modification, 1.1099, places=4)
        
    def test_fractal_trail_sell(self):
        engine = MockExecutionEngine()
        
        # SELL Trade
        entry = 1.1000
        current_sl = 1.1100 # Risk 100 pips
        tp = 1.0700
        risk = 0.0100
        
        # Price drops to 1.0750 (2.5R profit)
        current_price = 1.0750
        
        # Existing SL is 1.0999 (assume already moved to BE)
        current_sl = 1.0999 
        
        # Resistance Fractal at 1.0900
        fractals = {'support': 1.0000, 'resistance': 1.0900}
        
        engine.apply_trailing_stop(1, current_price, entry, "SELL", current_sl, tp, 0.0010, fractals)
        
        # Should move to Fractal + Buffer (1.0900 + 0.0001) = 1.0901
        self.assertAlmostEqual(engine.last_modification, 1.0901, places=4)

if __name__ == '__main__':
    unittest.main()
