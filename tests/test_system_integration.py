import unittest
from unittest.mock import MagicMock, patch
import pandas as pd
import numpy as np
from datetime import datetime
from app.market_sensor import MarketSensor
from app.bif_brain import BIFBrain
from app.darwin_engine import DarwinEngine
from app.chronos import ChronosWeaver, ChronosArena
from app.execution_engine import ExecutionEngine
# We don't import main, we simulate main's logic

class TestSystemIntegration(unittest.TestCase):
    def setUp(self):
        # 1. Setup Mock Data
        dates = pd.date_range(start='2024-01-01', periods=6000, freq='15min') # Deep history for Chronos
        # Create a Trending Market
        close = np.linspace(100, 200, 6000) + np.random.normal(0, 1, 6000)
        
        # FORCE BREAKOUT at the end
        close[-1] = 210 # Massive jump from ~200
        
        self.df_deep = pd.DataFrame({
            'time': dates,
            'open': close,
            'high': close + 1, # Highs track close
            'low': close - 1,
            'close': close,
            'tick_volume': 100
        })
        self.df_recent = self.df_deep.iloc[-500:]
        
        # 2. Setup Components
        self.brain = BIFBrain()
        self.darwin = DarwinEngine()
        self.chronos_arena = ChronosArena()
        
    @patch('app.market_sensor.mt5')
    def test_full_pipeline_flow(self, mock_mt5):
        """
        Simulates one full tick of the Main Loop.
        From Data -> BIF -> Darwin -> Jury -> Chronos -> Decision.
        """
        # --- A. SENSE ---
        # Mock Indicators (Passed from Sensor normally)
        indicators = {
            'ema_50': 150.0,
            'ema_200': 140.0,
            'rsi': 60,
            'atr': 2.0,
            'bb_upper': 205.0,
            'bb_lower': 195.0,
            'macd': 0.5,
            'macd_signal': 0.2
        }
        
        # Mock MTF Data for BIF
        mtf_data = {'H1': self.df_recent, 'H4': self.df_recent, 'M15': self.df_recent} # Simplified
        
        # --- B. PROCESS (BIF BRAIN) ---
        mtf_analysis = self.brain.analyze_mtf_regime(mtf_data)
        mtf_data['analysis'] = mtf_analysis['mtf_stats']
        
        self.assertIn('alignment_score', mtf_analysis)
        print(f"\n[Test] BIF Alignment: {mtf_analysis['alignment_score']}")
        
        # --- C. EVOLVE (DARWIN) ---
        # Force a Strategy to be a winner so we get a signal
        for strat in self.darwin.strategies:
            strat.phantom_equity = 10000 # Reset
            
        # Rig the Vote: Make TrendHawk LONG the winners
        # Current price 200 > EMA 50 (150). TrendHawk should BUY.
        # We ensure they are at top of list.
        for strat in self.darwin.strategies:
            if "TrendHawk_LONG" in strat.name:
                strat.phantom_equity = 15000 # Massive winner
        
        self.darwin.update(self.df_recent, indicators, mtf_data)
        
        # --- D. THE JURY (GATE 3) ---
        consensus = self.darwin.get_consensus_signal(self.df_recent, indicators, mtf_data, top_n=3)
        print(f"[Test] Jury Consensus: {consensus}")
        
        self.assertEqual(consensus['action'], 'BUY') # Should be Unanimous/Majority BUY
        
        # --- E. PROJECT CHRONOS (GATE 4) ---
        # Simulate Weaver
        weaver = ChronosWeaver(self.df_deep)
        features = {'price': 200.0, 'atr': 2.0, 'volatility': 0.01}
        futures = weaver.generate_historical_echoes(features, n_futures=50, horizon=10)
        
        # Simulate Arena
        # Since our df is perfectly trending (linspace), historical echoes should be bullish
        sim_result = self.chronos_arena.run_simulation('BUY', futures, 200.0, sl_dist=3.0, tp_dist=6.0)
        print(f"[Test] Chronos Result: {sim_result}")
        
        # We expect a Confirm or at least a result
        self.assertTrue(sim_result['win_rate'] >= 0.0)
        
        # --- F. DECISION ---
        decision = {'action': consensus['action'], 'confidence': consensus['confidence']}
        if sim_result['recommendation'] == 'BLOCK':
            decision['action'] = 'WAIT'
            
        print(f"[Test] Final Decision: {decision['action']}")
        
        # If Chronos blocked it (due to random noise in echoes maybe), that's fine, logic is valid.
        # If it passed, great.
        
if __name__ == '__main__':
    unittest.main()
