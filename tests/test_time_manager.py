import unittest
from datetime import datetime, timedelta
import pytz
from app.time_manager import TimeManager
from unittest.mock import MagicMock, patch

class TestTimeManager(unittest.TestCase):
    
    def setUp(self):
        self.tm = TimeManager()

    @patch('app.time_manager.datetime')
    def test_london_open(self, mock_datetime):
        # Mock 08:00 UTC (London Session) - Tuesday
        mock_now = datetime(2023, 10, 24, 8, 0, 0, tzinfo=pytz.UTC)
        mock_datetime.now.return_value = mock_now
        
        self.assertTrue(self.tm.is_market_open())
        self.assertEqual(self.tm.get_session_status(), "OPEN (London Session)")

    @patch('app.time_manager.datetime')
    def test_ny_overlap(self, mock_datetime):
        # Mock 14:00 UTC (Overlap) - Tuesday
        mock_now = datetime(2023, 10, 24, 14, 0, 0, tzinfo=pytz.UTC)
        mock_datetime.now.return_value = mock_now
        
        self.assertTrue(self.tm.is_market_open())
        self.assertTrue(self.tm.is_prime_time())
        self.assertEqual(self.tm.get_session_status(), "OPEN (London/NY Overlap - PRIME)")

    @patch('app.time_manager.datetime')
    def test_kill_zone_night(self, mock_datetime):
        # Mock 23:00 UTC (Asia/Night) - Tuesday
        mock_now = datetime(2023, 10, 24, 23, 0, 0, tzinfo=pytz.UTC)
        mock_datetime.now.return_value = mock_now
        
        self.assertFalse(self.tm.is_market_open())
        self.assertEqual(self.tm.get_session_status(), "CLOSED (Kill Zone/Night)")

    @patch('app.time_manager.datetime')
    def test_weekend(self, mock_datetime):
        # Mock Saturday
        mock_now = datetime(2023, 10, 28, 12, 0, 0, tzinfo=pytz.UTC) # Sat
        mock_datetime.now.return_value = mock_now
        
        self.assertFalse(self.tm.is_market_open())
        self.assertEqual(self.tm.get_session_status(), "CLOSED (Weekend)")

if __name__ == '__main__':
    unittest.main()
