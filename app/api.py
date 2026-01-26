from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import os
import json
import pandas as pd
from app.config import Config

app = FastAPI(title="Sentient Trader API")

# Enable CORS (for local React dev)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Allow all for local dev
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

STATE_FILE = os.path.join(Config.BASE_DIR, "system_state.json")
LOG_FILE = os.path.join(Config.BASE_DIR, "trade_log.csv")

@app.get("/")
def read_root():
    return {"status": "online", "service": "Sentient Trader API"}

@app.get("/state")
def get_system_state():
    """Returns the latest system heartbeat and market data."""
    if not os.path.exists(STATE_FILE):
        raise HTTPException(status_code=404, detail="System state not found (Bot syncing?)")
    
    try:
        with open(STATE_FILE, 'r') as f:
            data = json.load(f)
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/logs")
def get_trade_logs(limit: int = 50):
    """Returns the last N logs as a list of dicts."""
    if not os.path.exists(LOG_FILE):
        return []
    
    try:
        df = pd.read_csv(LOG_FILE, on_bad_lines='skip')
        if df.empty:
            return []
            
        # Ensure timestamp sorting
        if "Timestamp" in df.columns:
            # Sort desc
            # Convert to dict
            records = df.tail(limit).iloc[::-1].to_dict(orient="records")
            return records
        return []
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/history")
def get_market_history():
    """Returns the last 100 candles for charting."""
    history_file = os.path.join(Config.BASE_DIR, "market_history.json")
    if not os.path.exists(history_file):
        return []
        
    try:
        with open(history_file, 'r') as f:
            data = json.load(f)
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
