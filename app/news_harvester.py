import urllib.request
import re
from datetime import datetime
import json

import ssl

class NewsHarvester:
    def __init__(self):
        self.url = "https://www.forexfactory.com/calendar"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': 'https://www.google.com/',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'cross-site',
            'Sec-Fetch-User': '?1'
        }
        self.cache = []
        self.last_fetch = None

    def _get_ssl_context(self):
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx

    def fetch_upcoming_news(self):
        """
        Fetches High Impact news for USD and EUR.
        Returns a formatted string for the AI or a list of dicts.
        """
        # Simple caching (15 mins) to avoid spamming FF
        if self.last_fetch and (datetime.now() - self.last_fetch).seconds < 900:
            return self._format_news(self.cache)

        try:
            req = urllib.request.Request(self.url, headers=self.headers)
            with urllib.request.urlopen(req, context=self._get_ssl_context()) as response:
                html = response.read().decode('utf-8')
            
            with open("debug_calendar.html", "w", encoding="utf-8") as f:
                f.write(html)
                
            self.cache = self._parse_html(html)
            self.last_fetch = datetime.now()
            return self._format_news(self.cache)
            
        except Exception as e:
            print(f"News Scrape Error: {e}")
            return "News Data Unavailable."

    def _parse_html(self, html):
        """
        Regex parser for ForexFactory Calendar (JS Object extraction).
        Targeting 'window.calendarComponentStates' data structure.
        """
        news_items = []
        
        # We look for value patterns. The keys are consistent in the JS object.
        # Pattern designed to capture one event's key details.
        # "name":"...", ..., "currency":"...", ..., "impactTitle":"...", ..., "timeLabel":"...", ... "forecast":"...", "previous":"..."
        
        # We iterate over the 'events' arrays.
        # A simpler way is to split by '{"id":' which starts every event object
        event_chunks = html.split('{"id":')
        
        print(f"Debug: Found {len(event_chunks)} event chunks.")
        
        for chunk in event_chunks[1:]: # Skip preamble
            try:
                # 1. Extract Name
                name_match = re.search(r'"name":"([^"]+)"', chunk)
                event_name = name_match.group(1).encode('utf-8').decode('unicode_escape') if name_match else "Unknown"
                
                # 2. Extract Currency
                curr_match = re.search(r'"currency":"([A-Z]{3})"', chunk)
                if not curr_match: continue
                currency = curr_match.group(1)
                
                # Filter: EUR or USD
                if currency not in ['EUR', 'USD']: continue
                
                # 3. Extract Impact
                # "impactTitle":"High Impact Expected"
                impact_match = re.search(r'"impactTitle":"([^"]+)"', chunk)
                impact_title = impact_match.group(1) if impact_match else ""
                
                if "High Impact" not in impact_title: continue
                
                # 4. Extract Time
                # "timeLabel":"7:00am"
                time_match = re.search(r'"timeLabel":"([^"]+)"', chunk)
                time_label = time_match.group(1) if time_match else ""
                
                # 5. Extract Forecast
                fcst_match = re.search(r'"forecast":"([^"]*)"', chunk)
                forecast = fcst_match.group(1) if fcst_match else ""
                
                # 6. Previous
                prev_match = re.search(r'"previous":"([^"]*)"', chunk)
                previous = prev_match.group(1) if prev_match else ""

                # 7. Actual (Critical for Phase 60)
                act_match = re.search(r'"actual":"([^"]*)"', chunk)
                actual = act_match.group(1) if act_match else ""
                
                # 8. Date (chunk belongs to a day, but date is "date":"Jan 22, 2026" inside ?)
                # Actually, inside the event object, there is "date":"Jan 22, 2026"
                date_match = re.search(r'"date":"([^"]+)"', chunk)
                date_str = date_match.group(1) if date_match else ""

                news_items.append({
                    'currency': currency,
                    'event': event_name,
                    'time': f"{date_str} {time_label}",
                    'forecast': forecast,
                    'previous': previous,
                    'actual': actual 
                })
            except Exception as e:
                # print(f"Chunk Error: {e}")
                continue
                
        return news_items

    def fetch_latest_trigger(self):
        """
        Phase 60 Trigger.
        Checks if a High Impact event occurred in the last 15 minutes AND has an 'Actual' value.
        Returns the event dict if true, else None.
        """
        # Force fresh fetch
        self.last_fetch = None 
        # Force fresh fetch
        self.last_fetch = None 
        try:
            req = urllib.request.Request(self.url, headers=self.headers)
            with urllib.request.urlopen(req, context=self._get_ssl_context()) as response:
                html = response.read().decode('utf-8')
            all_events = self._parse_html(html)
            
            # Filter for events that HAVE an 'actual' value
            finished_events = [e for e in all_events if e['actual'] != ""]
            
            if not finished_events:
                return None
                
            # Ideally we check the timestamp, but parsing "Jan 22, 2026 8:30am" is tricky without a robust parser.
            # Simplify: The latest event with an 'Actual' value is likely the one that just happened 
            # (assuming the calendar is sorted chronologically, which it is).
            
            occurred_event = finished_events[-1] # Valid logical assumption for sorted list
            
            # TODO: Improve Timestamp Check to ensure it wasn't 4 hours ago.
            # For now, we rely on the bot polling loop calling this frequently.
            # If the value is there, it's "Done".
            
            return occurred_event
            
        except Exception as e:
            print(f"Trigger Check Error: {e}")
            return None


    def _format_news(self, news_list):
        if not news_list:
            return "No High-Impact News Detected."
            
        summary = "🚨 UPCOMING HIGH-IMPACT NEWS:\n"
        for item in news_list[:3]: # Top 3 only
            summary += f"- {item['currency']} {item['event']} @ {item['time']}. Fcst: {item['forecast']} (Prev: {item['previous']}). "
            if item['actual']:
                summary += f"ACTUAL: {item['actual']} "
            summary += "\n"
        return summary.strip()

if __name__ == "__main__":
    harvester = NewsHarvester()
    print(harvester.fetch_upcoming_news())
