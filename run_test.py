import os
import sys

# Disable telemetry and set absolute path
os.environ['DO_NOT_TELEMETRY'] = '1'
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.darwin_engine import DarwinEngine
import pandas as pd

def test_consensus():
    with open('test_jury_results.txt', 'w', encoding='utf-8') as f:
        f.write("Initializing Darwin Engine...\n")
        darwin = DarwinEngine()
        f.write(f"Total strategies loaded: {len(darwin.strategies)}\n")

        # Mock Data to trigger get_consensus_signal
        df = pd.DataFrame() 
        indicators = {}
        
        allowed = [
            "MeanReverter_LONG", "MeanReverter_SHORT", 
            "RSI_Matrix_LONG", "RSI_Matrix_SHORT", 
            "TrendHawk_LONG", "TrendHawk_SHORT", 
            "TrendPullback_LONG", "TrendPullback_SHORT", 
            "MACD_Cross_LONG", "MACD_Cross_SHORT", 
            "Sniper_Elite", "LiquiditySweeper_LONG"
        ]
        
        mtf_data = {
            'analysis': {
                'allowed_strategies': allowed
            }
        }

        # IMPORTANT: We need to set a dummy generate_signal function to not crash on empty df
        for strat in darwin.strategies:
            strat.generate_signal = lambda d, i, m: {'action': 'HOLD', 'reason': 'Test', 'sl': 0, 'tp': 0}

        # Execute LIVE logic!
        f.write("Calling DarwinEngine.get_consensus_signal()...\n")
        try:
            consensus_output = darwin.get_consensus_signal(df, indicators, mtf_data)
            f.write("\n=== CONSENSUS OUTPUT ===\n")
            f.write(str(consensus_output))
        except Exception as e:
            f.write(f"Error executing get_consensus_signal: {e}")

if __name__ == "__main__":
    test_consensus()
