import pandas as pd
import re

print("--- Analysis Report: Bot Performance ---")

# 1. Analyze trade_log_298327291.csv for the 498 BUYs
try:
    df = pd.read_csv('trade_log_298327291.csv')
    df_actions = df[df['Action'].isin(['BUY', 'SELL'])]
    print(f"\nTotal Executed Signals in log: {len(df_actions)}")
    print("\nAction Breakdown:")
    print(df_actions['Action'].value_counts())
    
    # 2. Extract strategy from Reasoning
    # Assuming Reasoning looks like: "MAJORITY BUY 2v0 (TrendHawk_SHORT...)"
    def extract_strategy(reason):
        if not isinstance(reason, str):
            return "Unknown"
        # Try to find the first strategy that voted BUY or SELL
        m = re.search(r'([A-Za-z0-9_]+):\s*(?:BUY|SELL)', reason)
        return m.group(1) if m else "Unknown"

    df_actions['Trigger_Strategy'] = df_actions['Reasoning'].apply(extract_strategy)
    print("\nTop Triggering Strategies:")
    print(df_actions['Trigger_Strategy'].value_counts().head(10))

except Exception as e:
    print(f"Error reading trade log: {e}")

# 3. Analyze logs.csv for Errors/Warnings
try:
    with open('logs.csv', 'r', encoding='utf-8') as f:
        lines = f.readlines()
        
    errors = [l.strip() for l in lines if re.search(r'(error|exception|fail)', l, re.IGNORECASE)]
    warnings = [l.strip() for l in lines if 'warning' in l.lower()]
    max_trades = [l.strip() for l in lines if 'MAX TRADES LIMIT HIT' in l]
    
    print("\n--- logs.csv System Health ---")
    print(f"Total Log Lines: {len(lines)}")
    print(f"Error Lines: {len(errors)}")
    print(f"Warning Lines: {len(warnings)}")
    print(f"Max Trades Hit Lines: {len(max_trades)}")
    
    if errors:
        print("\nTop 5 Recent Errors:")
        for e in errors[-5:]:
            print(e)
            
except Exception as e:
    print(f"Error reading logs.csv: {e}")

print("------------------------------------------")
