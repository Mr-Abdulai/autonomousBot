import time
import sys
from datetime import datetime, timedelta, timezone
import MetaTrader5 as mt5
import pandas as pd
from app.config import Config
from app.market_sensor import MarketSensor
from app.groq_strategist import GroqStrategist
from app.risk_manager import IronCladRiskManager
from app.execution_engine import ExecutionEngine
from app.dashboard_logger import DashboardLogger
from app.performance_analyzer import PerformanceAnalyzer
from app.time_manager import TimeManager
from app.bif_brain import BIFBrain
from app.darwin_engine import DarwinEngine

def main():
    print("=== Hybrid Neuro-Symbolic Trading System Starting ===")
    
    # 1. Validation
    try:
        Config.validate()
    except EnvironmentError as e:
        print(f"CRITICAL: {e}")
        sys.exit(1)
        
    # 2. Initialize Components
    sensor = MarketSensor(symbol=Config.SYMBOL, timeframe=Config.TIMEFRAME)
    ai_strategist = GroqStrategist(model="llama-3.3-70b-versatile")
    risk_manager = IronCladRiskManager()
    executor = ExecutionEngine()
    dashboard = DashboardLogger()
    perf_analyzer = PerformanceAnalyzer()
    time_manager = TimeManager()
    brain = BIFBrain()
    darwin = DarwinEngine() # Phase 83
    
    # 3. Connection Check
    if not sensor.initialize():
        print("CRITICAL: Failed to connect to MT5 for data feed. Exiting.")
        sys.exit(1)
        
    # SYNC SYMBOLS
    executor.symbol = sensor.symbol
    Config.SYMBOL = sensor.symbol
    print(f"System Initialized. Symbol: {Config.SYMBOL}, Timeframe: {Config.TIMEFRAME}")
    print("Entering Main Loop...")
    
    # 4. Main Loop
    while True:
        try:
            # Gather Account Info
            account_info = {
                "equity": 10000.0,
                "balance": 10000.0
            }
            if not Config.BACKTEST_MODE and mt5.initialize():
                acc = mt5.account_info()
                if acc:
                   account_info['equity'] = acc.equity
                   account_info['balance'] = acc.balance
            
            # One-time Sync for Risk Manager (Prevents "95% Daily Loss" on restart)
            if 'risk_synced' not in locals():
                 risk_manager.sync_start_balance(account_info['equity'])
                 locals()['risk_synced'] = True
            
            risk_manager.update_account_state(account_info['equity'])
            
            # A. SENSE
            df = sensor.get_market_data(n_candles=500)
            current_price = df.iloc[-1]['close']
            market_summary = sensor.get_market_summary()
            latest_indicators = sensor.get_latest_indicators()
            fractal_levels = sensor.get_latest_fractal_levels(df) # Phase 81
            
            # Phase 82: The Matrix (Multi-Timeframe Regime)
            mtf_data = sensor.fetch_mtf_data()
            mtf_analysis = brain.analyze_mtf_regime(mtf_data)
            
            # INJECT Regime for Darwin 2.0 (Smart Scoring)
            mtf_data['analysis'] = mtf_analysis['mtf_stats']
            
            bif_stats = mtf_analysis['mtf_stats']['M15']
            alignment_score = mtf_analysis['alignment_score']
            
            # Phase 83: Darwinian Evolution (Update Strategies)
            darwin.update(df, latest_indicators, mtf_data)
            leader_stats = darwin.get_leaderboard()
            
            # Enhance Market Summary for AI
            regime_tag = "UNKNOWN"
            if bif_stats['hurst'] > 0.55:
                regime_tag = "TRENDING (PERSISTENT)"
            elif bif_stats['hurst'] < 0.45:
                regime_tag = "MEAN REVERTING (CHOPPY)"
            else:
                regime_tag = "RANDOM WALK (NOISE)"
                
            if alignment_score < 0:
                 regime_tag += " [⛔ MTF MISMATCH - BLOCKED]"
            
            bif_context = f"""
=== MARKET REGIME ANALYSIS (BIF ENGINE) ===
Regime: {regime_tag}
Hurst Exponent: {bif_stats['hurst']} (Memory)
Shannon Entropy: {bif_stats['entropy']} (Signal Quality)
MTF Alignment Score: {alignment_score} (H1/H4 Confirmation)

=== DARWINIAN EVOLUTION (STRATEGY SELECTOR) ===
{leader_stats}
Current Leader: {darwin.leader.name}
"""
            market_summary += bif_context
            print(f"🧠 BIF Matrix: Score {alignment_score} | Leader: {darwin.leader.name}")

            # B. Check for active trades & Manage them
            atr_val = latest_indicators.get('atr', latest_indicators.get('ATR_14', 0.0))
            monitor_result = executor.monitor_open_trades(current_price, atr=atr_val, fractal_levels=fractal_levels)
            active_trades = monitor_result['trades'] 
            
            # C. Determine System State & Decision
            run_ai = True
            decision = {"action": "WAIT", "confidence_score": 0.0, "reasoning_summary": "Scanning..."}
            
            # Gate 0: Time Guard
            if not time_manager.is_market_open():
                 decision['reasoning_summary'] = f"Time Guard: {time_manager.get_session_status()}"
                 run_ai = False
            
            # Gate 1: Spread Guard
            if run_ai and not risk_manager.validate_spread(latest_indicators.get('spread', 0)):
                 decision['reasoning_summary'] = f"Spread High ({latest_indicators.get('spread',0)}). Paused."
                 run_ai = False

            # Gate 2: MTF Alignment Check (The Matrix)
            if run_ai and alignment_score < 0:
                 decision['reasoning_summary'] = f"⛔ MTF MISMATCH. Score {alignment_score}. Waiting."
                 run_ai = False
                 
            # Gate 3: Darwinian Signal
            if run_ai:
                darwin_signal = darwin.get_alpha_signal(df, latest_indicators, mtf_data)
                if darwin_signal['action'] == "HOLD":
                    reason = darwin_signal.get('reason', 'Waiting for setup')
                    print(f"⏳ Darwin Leader ({darwin.leader.name}) Waiting: {reason}")
                    decision['reasoning_summary'] = f"Darwin Leader ({darwin.leader.name}) says HOLD: {reason}"
                    run_ai = False
                else:
                    print(f"🔥 Darwin Leader ({darwin.leader.name}) Signals {darwin_signal['action']}!")
                    market_summary += f"\n[SIGNAL REQUEST] The Evolutionary Engine recommends {darwin_signal['action']} based on {darwin.leader.name} logic."

            # D. AI Strategy Layer (Groq)
            if run_ai:
                analyzed_decision = ai_strategist.get_trade_decision(market_summary, "")
                decision = risk_manager.validate_signal(analyzed_decision)
                
            # Log State
            dashboard.update_system_state(account_info, active_trades, latest_indicators, decision, bif_stats=bif_stats)
            dashboard.update_market_history(df)

            # E. Execution Logic
            if decision['action'] in ["BUY", "SELL"]:
                # Position Sizing
                atr = df.iloc[-1]['ATR_14']
                sl_mult = decision.get("stop_loss_atr_multiplier", 1.5)
                
                if decision['action'] == "BUY":
                    sl_price = current_price - (atr * sl_mult)
                    tp_price = current_price + ((current_price - sl_price) * 2.0)
                else:
                    sl_price = current_price + (atr * sl_mult)
                    tp_price = current_price - ((sl_price - current_price) * 2.0)

                risk_distance = abs(current_price - sl_price)
                if risk_distance > 0:
                    units = risk_manager.calculate_position_size(account_info["equity"], current_price, sl_price)
                    if units > 0:
                        executor.execute_trade(decision['action'], sl_price, tp_price, units)
            
            active_sleep = 5 if active_trades else 60
            time.sleep(active_sleep)

        except KeyboardInterrupt:
            print("Shutdown requested.")
            break
        except Exception as e:
            print(f"Loop Error: {e}")
            time.sleep(60)

if __name__ == "__main__":
    main()
