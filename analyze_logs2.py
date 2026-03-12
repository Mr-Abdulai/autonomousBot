import pandas as pd
import re

with open('final_log_report.txt', 'w', encoding='utf-8') as f_out:
    f_out.write("--- Analysis Report: Bot Performance ---\n")

    # 1. Analyze trade_log_298327291.csv
    try:
        df = pd.read_csv('trade_log_298327291.csv')
        df_actions = df[df['Action'].isin(['BUY', 'SELL'])]
        f_out.write(f"\nTotal Executed Signals in log: {len(df_actions)}\n")
        f_out.write("\nAction Breakdown:\n")
        f_out.write(df_actions['Action'].value_counts().to_string() + "\n")
        
        def extract_strategy(reason):
            if not isinstance(reason, str): return "Unknown"
            m = re.search(r'([A-Za-z0-9_]+):\s*(?:BUY|SELL)', reason)
            return m.group(1) if m else "Unknown"

        df_actions['Trigger_Strategy'] = df_actions['Reasoning'].apply(extract_strategy)
        f_out.write("\nTop Triggering Strategies:\n")
        f_out.write(df_actions['Trigger_Strategy'].value_counts().head(10).to_string() + "\n")

    except Exception as e:
        f_out.write(f"Error reading trade log: {e}\n")

    # 2. Analyze logs.csv
    try:
        with open('logs.csv', 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
        errors = [l.strip() for l in lines if re.search(r'(error|exception|fail)', l, re.IGNORECASE)]
        warnings = [l.strip() for l in lines if 'warning' in l.lower()]
        max_trades = [l.strip() for l in lines if 'MAX TRADES LIMIT HIT' in l]
        
        f_out.write("\n--- logs.csv System Health ---\n")
        f_out.write(f"Total Log Lines: {len(lines)}\n")
        f_out.write(f"Error Lines: {len(errors)}\n")
        f_out.write(f"Warning Lines: {len(warnings)}\n")
        f_out.write(f"Max Trades Hit Lines: {len(max_trades)}\n")
        
        if errors:
            f_out.write("\nTop 5 Recent Errors:\n")
            for e in errors[-5:]:
                f_out.write(e + "\n")
    except Exception as e:
        f_out.write(f"Error reading logs.csv: {e}\n")

    f_out.write("------------------------------------------\n")
