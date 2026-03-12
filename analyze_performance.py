import pandas as pd

files = ['trade_log.csv', 'trade_log_298327291.csv']

with open('analysis_report2.txt', 'w', encoding='utf-8') as f_out:
    for f in files:
        f_out.write(f"\n===== Inspecting {f} =====\n")
        try:
            df = pd.read_csv(f)
            f_out.write(f"Total Rows: {len(df)}\n")
            f_out.write(f"Columns: {df.columns.tolist()}\n")
            
            if 'Timestamp' in df.columns:
                df['Timestamp'] = pd.to_datetime(df['Timestamp'], errors='coerce')
                min_date = df['Timestamp'].min()
                max_date = df['Timestamp'].max()
                f_out.write(f"Date Range: {min_date} to {max_date}\n")
            
            # Action distribution
            action_col = 'Action' if 'Action' in df.columns else df.columns[2]
            f_out.write(f"\nTop 10 Actions:\n{df[action_col].value_counts().head(10).to_string()}\n")
            
            # PnL distribution
            if 'PnL' in df.columns:
                df['PnL'] = pd.to_numeric(df['PnL'], errors='coerce')
                pnl_non_null = df['PnL'].notna().sum()
                pnl_non_zero = (df['PnL'] != 0.0).sum()
                f_out.write(f"PnL Not Null: {pnl_non_null}, PnL != 0.0: {pnl_non_zero}\n")
                
                if pnl_non_zero > 0:
                    worst = df.sort_values('PnL').head(5)
                    f_out.write("\nWorst Trades Overall:\n")
                    f_out.write(worst[['Timestamp', action_col, 'PnL']].to_string(index=False) + "\n")
        except Exception as e:
            f_out.write(f"Error: {e}\n")
