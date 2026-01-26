import json
import csv
import os
import time
from datetime import datetime
from app.config import Config

class DashboardLogger:
    def __init__(self):
        self.state_file = os.path.join(Config.BASE_DIR, "system_state.json")
        self.log_file = os.path.join(Config.BASE_DIR, "trade_log.csv")
        self._initialize_csv()

    def _initialize_csv(self):
        """Creates the CSV header if file doesn't exist."""
        if not os.path.exists(self.log_file):
            with open(self.log_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                # Added 'PnL' column
                writer.writerow(["Timestamp", "Symbol", "Action", "Confidence", "Reasoning", "Entry", "SL", "TP", "Size", "PnL"])

    def update_system_state(self, account_info: dict, open_trades: list, market_data: dict = None, last_decision: dict = None, bif_stats: dict = None):
        """
        Writes the current heartbeat and extended state to JSON.
        market_data: Optional dict containing latest indicators (RSI, MACD, etc)
        bif_stats: Optional dict containing HMM/Entropy/Hurst
        """
        state = {
            "last_heartbeat": datetime.now().isoformat(),
            "status": "ONLINE",
            "symbol": Config.SYMBOL,
            "risk_per_trade": Config.RISK_PER_TRADE,
            "active_trades": self._enrich_trades_with_pips(open_trades),
            # Account Details
            "equity": account_info.get("equity", 0.0),
            "balance": account_info.get("balance", 0.0),
            "leverage": account_info.get("leverage", 1),
            "margin": account_info.get("margin", 0.0),
            "margin_free": account_info.get("margin_free", 0.0),
            "name": account_info.get("name", "Unknown"),
            "server": account_info.get("server", "Unknown"),
            "currency": account_info.get("currency", "USD"),
            "profit": account_info.get("profit", 0.0), # Current floating PnL
            # Historical PnL
            "daily_pnl": account_info.get("daily_pnl", 0.0),
            "total_pnl": account_info.get("total_pnl", 0.0),
            # Market Data Snapshot
            "market_data": market_data if market_data else {},
            "bif_analysis": bif_stats if bif_stats else {},
            # AI Decision
            "last_decision": {
                "action": last_decision.get("action", "WAIT") if last_decision else "WAIT",
                "confidence": last_decision.get("confidence_score", 0.0) if last_decision else 0.0,
                "reasoning": last_decision.get("reasoning_summary", "Initializing...") if last_decision else "Waiting for signal..."
            }
        }
        
        temp_file = self.state_file + ".tmp"
        try:
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(state, f, indent=4)
            os.replace(temp_file, self.state_file)
        except Exception as e:
            print(f"Error writing system state: {e}")

    def update_market_history(self, df):
        """Saves the last 100 candles for charting."""
        history_file = os.path.join(Config.BASE_DIR, "market_history.json")
        try:
            # Keep last 100 rows, selective columns
            if df is not None and not df.empty:
                history = df.tail(100)[['time', 'open', 'high', 'low', 'close', 'EMA_50', 'EMA_200']].copy()
                # Convert timestamp to string
                if 'time' in history.columns:
                     history['time'] = history['time'].astype(str)
                
                # Pandas to json records
                history.to_json(history_file, orient="records")
        except Exception as e:
            print(f"History Save Error: {e}")

    def log_decision(self, decision: dict, execution_info: dict = None, pnl: float = 0.0):
        """
        Appends a row to the trade log CSV.
        """
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            action = decision.get("action", "HOLD")
            confidence = decision.get("confidence_score", 0.0)
            reasoning = decision.get("reasoning_summary", "").replace("\n", " ")
            
            entry = execution_info.get("open_price", 0.0) if execution_info else 0.0
            sl = execution_info.get("sl", 0.0) if execution_info else decision.get("sl", 0.0)
            tp = execution_info.get("tp", 0.0) if execution_info else 0.0
            size = execution_info.get("volume", 0.0) if execution_info else 0.0

            with open(self.log_file, 'a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    timestamp, 
                    Config.SYMBOL, 
                    action, 
                    f"{confidence:.2f}", 
                    reasoning, 
                    entry, 
                    sl, 
                    tp, 
                    size,
                    pnl # New PnL field (0.0 for opens, actual value for CLOSE/TP/SL)
                ])
        except Exception as e:
            print(f"Error logging decision: {e}")

    def _enrich_trades_with_pips(self, trades: list) -> list:
        """Helper to append SL/TP in pips for dashboard display."""
        enriched = []
        is_jpy = "JPY" in Config.SYMBOL
        multiplier = 100 if is_jpy else 10000
        
        for t in trades:
            try:
                # Copy to avoid mutating original list affecting execution engine
                trade = t.copy()
                open_price = trade.get('open_price', 0)
                sl = trade.get('sl', 0)
                tp = trade.get('tp', 0)
                
                if open_price > 0:
                    if sl > 0:
                        trade['sl_pips'] = abs(open_price - sl) * multiplier
                    if tp > 0:
                        trade['tp_pips'] = abs(open_price - tp) * multiplier
                
                enriched.append(trade)
            except Exception as e:
                enriched.append(t) # Fallback
                
        return enriched

if __name__ == "__main__":
    pass
