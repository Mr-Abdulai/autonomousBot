import pandas as pd

df = pd.read_csv('trade_log_298327291.csv')
buys = df[df['Action'] == 'BUY']

with open('research_output.txt', 'w', encoding='utf-8') as f:
    f.write("--- TOP 5 BUYS ---\n")
    for idx, row in buys.head(5).iterrows():
        reason = str(row['Reasoning']).encode('ascii', 'ignore').decode()  # Remove emojis
        f.write(f"[{row['Timestamp']}] {row['Action']} | Conf: {row['Confidence']} | Entry: {row['Entry']} | SL: {row['SL']} | TP: {row['TP']} | Size: {row['Size']} | Reason: {reason}\n")
    
    f.write("\nTotal non-zero PnL: " + str(len(df[df['PnL'] != 0.0])))
