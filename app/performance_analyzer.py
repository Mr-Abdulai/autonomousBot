import pandas as pd
import os
from app.config import Config

class PerformanceAnalyzer:
    def __init__(self):
        self.log_file = os.path.join(Config.BASE_DIR, "trade_log.csv")

    def get_performance_summary(self) -> str:
        """
        Reads the trade log and returns a natural language summary of performance.
        Designed to be fed into the AI's prompt.
        """
        if not os.path.exists(self.log_file):
            return "No trading history available yet. This is your first session."

        try:
            df = pd.read_csv(self.log_file)
            if df.empty:
                 return "No trading history available yet."
            
            # Ensure PnL column exists
            if "PnL" not in df.columns:
                return "Trading history exists but lacks PnL data."

            # Filter for Closed Trades (PnL != 0)
            closed_trades = df[df["PnL"] != 0].copy()
            
            if closed_trades.empty:
                return "No closed trades yet. Only open positions or holds."

            # Calculate Stats
            total_trades = len(closed_trades)
            wins = len(closed_trades[closed_trades["PnL"] > 0])
            losses = len(closed_trades[closed_trades["PnL"] < 0])
            win_rate = (wins / total_trades) * 100
            net_pnl = closed_trades["PnL"].sum()
            
            # Get Last 3 Trades for Recency Bias
            last_3 = closed_trades.tail(3)
            recent_context = []
            for _, row in last_3.iterrows():
                outcome = "WIN" if row['PnL'] > 0 else "LOSS"
                recent_context.append(f"{outcome} ({row['Action']} on {row['Symbol']}, PnL: ${row['PnL']:.2f})")
            
            recent_str = ", ".join(recent_context)

            summary = (
                f"PAST PERFORMANCE CONTEXT:\n"
                f"- Total Closed Trades: {total_trades}\n"
                f"- Win Rate: {win_rate:.1f}%\n"
                f"- Net Realized PnL: ${net_pnl:.2f}\n"
                f"- Recent Outcomes: {recent_str}.\n"
                f"Reflect on these results. If you are losing, be more conservative. If winning, maintain discipline."
            )
            
            return summary

        except Exception as e:
            return f"Error reading performance history: {e}"
