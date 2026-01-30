from datetime import datetime, time
import pytz
from app.config import Config

class TimeManager:
    """
    Phase 67: The Clock.
    Manages Trading Sessions and enforces 'Kill Zones'.
    Uses UTC strictly to avoid local time confusion.
    """

    # Session Definitions (UTC)
    # London: 07:00 - 16:00
    # NY: 12:00 - 21:00
    # Overlap: 12:00 - 16:00 (Prime Time)
    
    # We trade from London Open (07:00) to NY Close (21:00).
    # We SLEEP during Asia (21:00 - 07:00) to avoid low liquidity/spreads.
    OPEN_HOUR = 7
    CLOSE_HOUR = 21

    def __init__(self):
        self.timezone = pytz.UTC

    def get_current_time(self) -> datetime:
        """Returns current aware datetime in UTC."""
        return datetime.now(self.timezone)

    def is_market_open(self) -> bool:
        """
        Global Master Switch.
        Returns True if within trading hours (London Start -> NY End).
        Returns False if in Kill Zone (Night/Asia) or Weekend.
        """
        if Config.OVERRIDE_TIME_GUARD:
            return True

        now = self.get_current_time()

        # 1. Weekend Check (Friday 22:00 UTC - Sunday 22:00 UTC is usually Forex closed)
        # Simplified: Saturday (5) and Sunday (6) are closed.
        if now.weekday() >= 5: 
            return False

        # 2. Hour Check
        current_hour = now.hour

        # Allow trading if hour is >= 7 AND hour < 21
        # 07:00 is YES. 20:59 is YES. 21:00 is NO.
        if self.OPEN_HOUR <= current_hour < self.CLOSE_HOUR:
            return True
        
        return False

    def get_session_status(self) -> str:
        """Returns human-readable session status."""
        if not self.is_market_open():
            now = self.get_current_time()
            if now.weekday() >= 5:
                return "CLOSED (Weekend)"
            else:
                return "CLOSED (Kill Zone/Night)"
        
        now = self.get_current_time()
        hour = now.hour
        
        if 7 <= hour < 12:
            return "OPEN (London Session)"
        elif 12 <= hour < 16:
            return "OPEN (London/NY Overlap - PRIME)"
        elif 16 <= hour < 21:
            return "OPEN (NY Session)"
        
        return "OPEN (Unknown Session)"

    def is_prime_time(self) -> bool:
        """Returns True if in London/NY Overlap (12:00 - 16:00 UTC)."""
        now = self.get_current_time()
        return 12 <= now.hour < 16


class SessionOptimizer:
    """
    PHASE 5B: Session-Based Trading Optimization
    Adjusts strategy parameters based on market session
    Optimizes for liquidity and volatility characteristics
    """
    
    SESSIONS = {
        "LONDON": {
            "hours": (7, 16),
            "risk_mult": 1.2,  # Higher volume = can take bigger positions
            "best_pairs": ["EURUSD", "GBPUSD", "EURGBP"],
            "description": "European session - highest EUR/GBP volume"
        },
        "NEW_YORK": {
            "hours": (13, 22),
            "risk_mult": 1.0,  # Standard risk
            "best_pairs": ["EURUSD", "GBPUSD", "USDJPY", "USDCAD"],
            "description": "US session - USD pairs active"
        },
        "OVERLAP": {
            "hours": (13, 16),  # London/NY overlap
            "risk_mult": 1.3,  # Peak liquidity = highest risk tolerance
            "best_pairs": ["EURUSD", "GBPUSD"],
            "description": "Prime time - maximum liquidity"
        },
        "ASIAN": {
            "hours": (22, 7),  # Wraps midnight
            "risk_mult": 0.7,  # Lower volume = reduce risk
            "best_pairs": ["USDJPY", "AUDUSD", "NZDUSD"],
            "description": "Asia-Pacific session - lower liquidity"
        }
    }
    
    def __init__(self):
        self.timezone = pytz.UTC
    
    def get_current_session(self) -> dict:
        """Returns current session info with parameters"""
        now = datetime.now(self.timezone)
        hour = now.hour
        
        # Check overlap first (most restrictive range)
        if 13 <= hour < 16:
            return {"name": "OVERLAP", **self.SESSIONS["OVERLAP"]}
        
        # Check other sessions
        for session_name, params in self.SESSIONS.items():
            if session_name == "OVERLAP":
                continue
                
            start, end = params["hours"]
            
            # Handle wrap-around (Asian session)
            if start > end:  # e.g., 22 to 7
                if hour >= start or hour < end:
                    return {"name": session_name, **params}
            else:
                if start <= hour < end:
                    return {"name": session_name, **params}
        
        return {"name": "UNKNOWN", "risk_mult": 0.5, "best_pairs": [], "description": "Unknown session"}
    
    def get_risk_multiplier(self) -> float:
        """Returns session-based risk multiplier"""
        session = self.get_current_session()
        return session["risk_mult"]
    
    def is_pair_optimal(self, symbol: str) -> bool:
        """Check if symbol is optimal for current session"""
        session = self.get_current_session()
        
        # Normalize symbol (remove broker suffixes)
        base_symbol = self._normalize_symbol(symbol)
        
        return base_symbol in session["best_pairs"]
    
    def get_session_boost(self, symbol: str) -> float:
        """
        Returns confidence boost for trading this pair in current session
        +0.1 if optimal pair, 0.0 if neutral, -0.1 if suboptimal
        """
        session = self.get_current_session()
        base_symbol = self._normalize_symbol(symbol)
        
        if base_symbol in session["best_pairs"]:
            return 0.1  # Boost confidence
        
        # Check if it's a bad match (e.g., EUR pair in Asian session)
        if session["name"] == "ASIAN" and ("EUR" in base_symbol or "GBP" in base_symbol):
            return -0.1  # Penalize
        
        return 0.0  # Neutral
    
    def _normalize_symbol(self, symbol: str) -> str:
        """
        Normalize broker-specific symbol names
        Exness: EURUSDm -> EURUSD
        IC Markets: EURUSD.r -> EURUSD
        """
        # Remove common suffixes
        symbol = symbol.upper()
        suffixes = ['M', '.R', '.RAW', '-SB', '_SB', '.ECN', '.PRO']
        
        for suffix in suffixes:
            if symbol.endswith(suffix):
                symbol = symbol[:-len(suffix)]
        
        return symbol
