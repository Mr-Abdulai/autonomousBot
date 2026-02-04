
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
        # Force Reset HWM to current equity to avoid inheriting 'Deep Drawdown' state from default $10k
        self.high_water_mark = equity
            
        # 2. Calculate Drawdowns
        if self.high_water_mark > 0:
            drawdown = (self.high_water_mark - equity)
            self.current_drawdown_pct = (drawdown / self.high_water_mark) * 100.0
        else:
            self.current_drawdown_pct = 0.0
            
        # Daily Drawdown
        if self.start_of_day_equity > 0:
            daily_loss = self.start_of_day_equity - equity
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
        # UPDATED: Lowered from 0.70 to match jury's partial agreement (1/3 votes = 0.5 confidence)
        self.min_confidence = 0.50
        self.last_trade_time = 0
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
        
        # 0. COOLDOWN (Anti-Chopping)
        # Prevent rapid-fire entries (e.g. Buy then Sell in 2 mins)
        import time
        now = time.time()
        if action != "HOLD" and (now - self.last_trade_time < 300): # 5 Minutes
            # UNLESS it's a News Signal (Priority)
            if "NEWS" not in decision.get('reasoning_summary', ''):
                print(f"RiskManager: Cooldown Active ({int(300 - (now - self.last_trade_time))}s rem). Holding.")
                decision['action'] = "HOLD"
                decision['reasoning_summary'] = "Cooldown Active (Anti-Chop)"
                return decision
        
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
            
        # If passed all checks, update last trade time
        if decision['action'] != "HOLD":
            self.last_trade_time = now
            
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

    def calculate_kelly_position(self, win_rate: float, avg_win: float, avg_loss: float, equity: float, current_price: float, sl_price: float) -> float:
        """
        PHASE 5B: Kelly Criterion for optimal position sizing
        Kelly Formula: f* = (p*b - q) / b
        where:
            p = win probability (win_rate)
            b = win/loss ratio (avg_win / avg_loss)
            q = loss probability (1 - win_rate)
        
        Uses Half-Kelly for conservative approach
        """
        try:
            # Fallback to standard method if insufficient data
            if win_rate <= 0.5 or avg_loss == 0 or avg_win == 0:
                print("📉 Kelly: Insufficient edge, using standard sizing")
                return self.calculate_position_size(equity, current_price, sl_price)
            
            # Calculate Kelly criterion
            b = avg_win / avg_loss  # Win/Loss ratio (e.g., 2.0 for 2R avg win vs 1R avg loss)
            q = 1 - win_rate
            kelly_fraction = (win_rate * b - q) / b
            
            # Sanity check - Kelly shouldn't be negative or > 0.25
            if kelly_fraction <= 0:
                print(f"📉 Kelly: No edge detected (fraction={kelly_fraction:.3f}), using min size")
                return self.calculate_position_size(equity, current_price, sl_price) * 0.5
            
            # Apply Half-Kelly (more conservative, reduces variance)
            safe_kelly = kelly_fraction * 0.5
            
            # Cap at 2% max for safety (vs 1% standard)
            kelly_risk_pct = min(safe_kelly, 0.02)
            
            # Calculate position size using Kelly risk %
            risk_amount = equity * kelly_risk_pct
            risk_per_unit = abs(current_price - sl_price)
            
            if risk_per_unit == 0:
                return 1.0 # Minimal unit
            
            units = risk_amount / risk_per_unit
            
            print(f"📊 Kelly Criterion: WR={win_rate:.1%}, B={b:.2f}, Kelly={kelly_fraction:.3f}, Half-Kelly={safe_kelly:.3f}")
            print(f"💰 Kelly Position: {kelly_risk_pct:.2%} risk = {units:.2f} units (vs {self.risk_per_trade:.2%} standard)")
            
            return units
            
        except Exception as e:
            print(f"Kelly Calculation Error: {e}, falling back to standard sizing")
            return self.calculate_position_size(equity, current_price, sl_price)

    def validate_spread(self, spread_points: int, max_spread: int = 20) -> bool:
        """
        Returns False if spread is too high.
        GOLD: Default 50 points (5 pips) vs 20 points for forex
        Protects against News spikes and Rollover hours.
        """
        if spread_points > max_spread:
            return False
        return True
