import pandas as pd
import urllib.request
import io

url = "https://www.forexfactory.com/calendar"
headers = {
    'User-Agent': 'Mozilla/5.0'
}

try:
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req) as response:
        content = response.read()
        
    # Pandas read_html
    dfs = pd.read_html(io.BytesIO(content))
    print(f"Found {len(dfs)} tables.")
    if len(dfs) > 0:
        print(dfs[0].head())
        
except Exception as e:
    print(f"Pandas Error: {e}")
