from app.config import Config

class IronCladRiskManager:
    def __init__(self):
        self.risk_per_trade = Config.RISK_PER_TRADE
        self.min_confidence = 0.70

    def validate_signal(self, decision: dict) -> dict:
        """
        Filters the AI decision based on strict risk rules.
        """
        confidence = decision.get("confidence_score", 0.0)
        action = decision.get("action", "HOLD")
        
        if confidence < self.min_confidence:
            print(f"RiskManager: Confidence {confidence:.2f} < {self.min_confidence}. Overriding to HOLD.")
            decision['action'] = "HOLD"
            decision['reasoning_summary'] = f"[RISK OVERRIDE] Low confidence ({confidence:.2f}). Original: {decision.get('reasoning_summary')}"
            
        return decision

    def calculate_position_size(self, account_equity: float, entry_price: float, stop_loss_price: float) -> float:
        """
        Calculates position size in UNITS (not lots yet, unless 1 unit = 1 lot).
        Formula: (Equity * Risk_Percent) / |Entry - SL|
        """
        if entry_price <= 0 or stop_loss_price <= 0:
            return 0.0
            
        distance = abs(entry_price - stop_loss_price)
        if distance == 0:
            return 0.0
            
        risk_amount = account_equity * self.risk_per_trade
        position_size_units = risk_amount / distance
        
        # Monitor: Sanity check for extremely large positions
        # e.g. if SL is too tight.
        
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
