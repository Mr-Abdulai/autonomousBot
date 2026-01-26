import urllib.request
import urllib.error

url = "https://www.forexfactory.com/calendar"
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8'
}

try:
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req) as response:
        content = response.read().decode('utf-8')
        print("Success! Content length:", len(content))
        # Print a snippet to verify it's not a captcha page
        if "calendar__table" in content:
            print("Found calendar table.")
        else:
            print("Warning: Calendar table not found in HTML.")
            
except urllib.error.HTTPError as e:
    print(f"HTTP Error: {e.code} - {e.reason}")
except Exception as e:
    print(f"Error: {e}")
