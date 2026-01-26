from datetime import datetime, time
import pytz

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
