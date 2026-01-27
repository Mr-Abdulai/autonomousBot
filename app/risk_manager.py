
from app.config import Config

class EquityCurveManager:
    """
    Phase 68: The Shield.
    Tracks Account Health, High Water Mark, and Drawdown.
    Determines if we are in 'Survival Mode' or 'Growth Mode'.
    """
    def __init__(self, initial_equity: float = 10000.0):
        self.high_water_mark = initial_equity
        self.start_of_day_equity = initial_equity
        self.current_drawdown_pct = 0.0
        self.daily_drawdown_pct = 0.0
        
    def update(self, current_equity: float, is_new_day: bool = False):
        """Called every loop to update state."""
        if is_new_day:
            self.start_of_day_equity = current_equity
            
        # 1. Update High Water Mark (HWM)
        if current_equity > self.high_water_mark:
            self.high_water_mark = current_equity
            
    def sync_balance(self, equity: float):
        """Called on startup to sync internal state with Live Account."""
        print(f"RiskManager: Syncing Start Equity to Live Balance: ${equity:.2f}")
        self.start_of_day_equity = equity
        self.high_water_mark = max(self.high_water_mark, equity)
            
        # 2. Calculate Drawdowns
        if self.high_water_mark > 0:
            drawdown = (self.high_water_mark - current_equity)
            self.current_drawdown_pct = (drawdown / self.high_water_mark) * 100.0
        else:
            self.current_drawdown_pct = 0.0
            
        # Daily Drawdown
        if self.start_of_day_equity > 0:
            daily_loss = self.start_of_day_equity - current_equity
            self.daily_drawdown_pct = (daily_loss / self.start_of_day_equity) * 100.0
        else:
            self.daily_drawdown_pct = 0.0

    def get_risk_scale_factor(self, is_making_ath: bool = False) -> float:
        """
        Returns a multiplier for position size.
        """
        # A. SURVIVAL MODE (Deep Drawdown > 10%)
        if self.current_drawdown_pct > 10.0:
            return 0.25 # Slash risk by 75%
            
        # B. DEFENSIVE MODE (Drawdown > 5%)
        elif self.current_drawdown_pct > 5.0:
            return 0.50 # Slash risk by 50%
            
        # C. GROWTH MODE (Making New Highs)
        # If we are within 1% of HWM, consider it "ATH Zone"
        elif self.current_drawdown_pct < 1.0:
            return 1.5 # Boost risk by 50% (Compound)
            
        # D. STANDARD MODE
        return 1.0

    def check_circuit_breaker(self) -> bool:
        """Returns True if Daily Loss Limit exceeded."""
        if self.daily_drawdown_pct > (Config.MAX_DAILY_LOSS * 100):
            return True
        return False


class IronCladRiskManager:
    def __init__(self):
        self.risk_per_trade = Config.RISK_PER_TRADE
        self.min_confidence = 0.70
        self.equity_manager = EquityCurveManager() # Initialize

    def update_account_state(self, equity: float, is_new_day: bool = False):
        self.equity_manager.update(equity, is_new_day)
        
    def sync_start_balance(self, equity: float):
         self.equity_manager.sync_balance(equity)

    def validate_signal(self, decision: dict) -> dict:
        """
        Filters the AI decision based on strict risk rules.
        """
        confidence = decision.get("confidence_score", 0.0)
        action = decision.get("action", "HOLD")
        
        # 1. CIRCUIT BREAKER
        if self.equity_manager.check_circuit_breaker():
            print("🚨 CIRCUIT BREAKER HIT: Max Daily Loss Exceeded. BLOCKING TRADES.")
            decision['action'] = "HOLD"
            decision['reasoning_summary'] = f"🚨 DAILY LOSS LIMIT HIT ({self.equity_manager.daily_drawdown_pct:.2f}%). HALTED."
            return decision

        # 2. CONFIDENCE CHECK
        if confidence < self.min_confidence:
            print(f"RiskManager: Confidence {confidence:.2f} < {self.min_confidence}. Overriding to HOLD.")
            decision['action'] = "HOLD"
            decision['reasoning_summary'] = f"[RISK OVERRIDE] Low confidence ({confidence:.2f}). Original: {decision.get('reasoning_summary')}"
            
        return decision

    def calculate_position_size(self, account_equity: float, entry_price: float, stop_loss_price: float) -> float:
        """
        Calculates position size in UNITS.
        Applies Dynamic Risk Scaling from EquityCurveManager.
        """
        if entry_price <= 0 or stop_loss_price <= 0:
            return 0.0
            
        distance = abs(entry_price - stop_loss_price)
        if distance == 0:
            return 0.0
        
        # --- DYNAMIC RISK SCALING ---
        scale_factor = 1.0
        if Config.ENABLE_DYNAMIC_RISK:
            scale_factor = self.equity_manager.get_risk_scale_factor()
            
        final_risk_pct = self.risk_per_trade * scale_factor
        risk_amount = account_equity * final_risk_pct
        
        position_size_units = risk_amount / distance
        
        if scale_factor != 1.0:
            print(f"🛡️ Dynamic Risk Active: Factor {scale_factor}x. Risking {final_risk_pct*100:.2f}% (${risk_amount:.2f}).")
        
        return position_size_units

    def check_stop_loss_validity(self, entry: float, sl: float, action: str) -> bool:
        """Sanity check that SL is on the correct side of Entry."""
        if action == "BUY" and sl >= entry:
            return False
        if action == "SELL" and sl <= entry:
            return False
        return True

    def check_stacking_safety(self, active_trades: list) -> bool:
        """
        Returns True ONLY if all active trades are 'Risk Free' (SL at or better than Entry).
        Allows for 'Pyramiding'.
        """
        if not active_trades:
            return True # Safe to open first trade
            
        for trade in active_trades:
            action = trade.get('action')
            entry = trade.get('open_price')
            sl = trade.get('sl')
            
            # Check if this trade is still "at risk"
            # Buy: SL must be >= Entry
            if action == "BUY" and sl < entry:
                return False
            # Sell: SL must be <= Entry
            if action == "SELL" and sl > entry:
                return False
                
        return True

    def validate_spread(self, spread_points: int, max_spread: int = 20) -> bool:
        """
        Returns False if spread is too high (e.g. > 2.0 pips / 20 points).
        Protects against News spikes and Rollover hours.
        """
        if spread_points > max_spread:
            return False
        return True
