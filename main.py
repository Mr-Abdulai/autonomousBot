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
from app.chronos import ChronosWeaver, ChronosArena
from app.oracle import Oracle

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
    oracle = Oracle(ai_strategist) # Phase 90
    
    # CHRONOS ENGINE
    chronos_arena = ChronosArena()
    
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
            # ... (Account Info & Risk Sync preserved in previous blocks, skipped here for brevity)
            
             # One-time Sync for Risk Manager
            if 'risk_synced' not in locals():
                 risk_manager.sync_start_balance(account_info['equity'])
                 locals()['risk_synced'] = True
            
            risk_manager.update_account_state(account_info['equity'])

            # ... (News Radar Check Logic preserved, assume it's above A. SENSE)
            
            # A. SENSE (Upgraded for Chronos Pro)
            # Fetch Deep History for The Weaver
            df_deep = sensor.get_market_data(n_candles=5000) 
            df = df_deep.iloc[-500:] # subset for indicators to stay fast
            
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
            
            # --- NEWS OVERRIDE ---
            if news_signal:
                print("⚡ NEWS INTERVENTION: Skipping Technical Gates.")
                decision = news_signal
                decision['confidence_score'] = 1.0 # Max Confidence
                decision['stop_loss_atr_multiplier'] = 2.0 # Volatility Buffer
                run_ai = False # Skip Standard AI
            
            # Gate 0: Time Guard
            if not time_manager.is_market_open():
                 decision['reasoning_summary'] = f"Time Guard: {time_manager.get_session_status()}"
                 run_ai = False
                 # Note: News might happen pre-market? Unlikely for major pairs usually inside session, but be careful.
            
            # Gate 1: Spread Guard (Critical during News)
            if (run_ai or news_signal) and not risk_manager.validate_spread(latest_indicators.get('spread', 0)):
                 decision['reasoning_summary'] = f"Spread High ({latest_indicators.get('spread',0)}). Paused."
                 run_ai = False
                 if news_signal:
                     print("❌ News Trade Aborted due to Spread Spike.")
                     decision['action'] = "WAIT"

            # Gate 2: MTF Alignment Check (The Matrix)
            # IGNORE IF NEWS SIGNAL
            if run_ai and not news_signal and alignment_score < 0:
                 decision['reasoning_summary'] = f"⛔ MTF MISMATCH. Score {alignment_score}. Waiting."
                 run_ai = False
                 
            # Gate 3: Darwinian Signal (The Jury Protocol)
            if run_ai:
                darwin_signal = darwin.get_consensus_signal(df, latest_indicators, mtf_data)
                
                if darwin_signal['action'] == "HOLD":
                    reason = darwin_signal.get('reason', 'Jury Voted HOLD')
                    print(f"⚖️ Jury Verdict: HOLD ({reason})")
                    decision['reasoning_summary'] = f"Jury Veto: {reason}"
                    run_ai = False
                else:
                    conf = darwin_signal.get('confidence', 0.8)
                    print(f"🔥 Jury Verdict: {darwin_signal['action']} (Confidence: {conf}) | {darwin_signal['reason']}")
                    market_summary += f"\n[SIGNAL REQUEST] The Jury recommends {darwin_signal['action']} (Confidence {conf}). Logic: {darwin_signal['reason']}"
                    
                    # Pass Confidence to Decision
                    decision['confidence_score'] = conf
                    # IMPORTANT: Tentatively set action so Chronos knows what to test, 
                    # though AI (Group D) has final say, we test the Jury's intent.
                    decision['action'] = darwin_signal['action'] 

            # Gate 4: Project Chronos (The Time Chamber)
            if run_ai and decision.get('action') in ['BUY', 'SELL']:
                 print(f"⏳ Chronos: Simulating {decision['action']} in 100 Parallel Futures...")
                 weaver = ChronosWeaver(df_deep) # Init with deep history
                 
                 # Prepare Features for Pro Engine
                 current_features = {
                     'price': current_price,
                     'atr': atr_val,
                     'volatility': atr_val / current_price if current_price > 0 else 0.001
                 }
                 
                 # Generate Futures (Tries Pro, falls back to Lite)
                 # Horizon: 12 candles (3 Hours)
                 futures = weaver.generate_historical_echoes(current_features, n_futures=100, horizon=12)
                 
                 # Estimate SL/TP for Simulation (Standard 1.5 ATR risk)
                 est_sl_dist = atr_val * 1.5
                 est_tp_dist = est_sl_dist * 2.0
                 
                 sim_result = chronos_arena.run_simulation(
                     decision['action'], 
                     futures, 
                     current_price, 
                     est_sl_dist, 
                     est_tp_dist
                 )
                 
                 if sim_result['recommendation'] == 'BLOCK':
                     print(f"🛑 Chronos VETO: Win Rate {sim_result['win_rate']:.2f} in Simulation. Risk too High.")
                     decision['reasoning_summary'] = f"Chronos Veto (WR {sim_result['win_rate']:.2f})"
                     decision['action'] = "WAIT" # Reset
                     run_ai = False
                 else:
                     print(f"✅ Chronos CONFIRM: Win Rate {sim_result['win_rate']:.2f} (Survival {sim_result['survival_rate']:.2f})")
                     market_summary += f"\n[CHRONOS] Simulation confirmed {decision['action']}. Win Probability: {sim_result['win_rate']:.0%}."


            # D. AI Strategy Layer (Groq)
            if run_ai:
                analyzed_decision = ai_strategist.get_trade_decision(market_summary, "")
                decision = risk_manager.validate_signal(analyzed_decision)
                
            # Log State
            swarm_state = darwin.get_swarm_state()
            
            # ORACLE BRIEFING
            brief = oracle.generate_brief(
                market_data=latest_indicators, # FIX: Pass Dict, not Str
                regime={"trend": regime_tag, "summary": bif_context},
                leader_name=darwin.leader.name,
                active_trades=active_trades
            )
            
            dashboard.update_system_state(account_info, active_trades, latest_indicators, decision, bif_stats=bif_stats, swarm_state=swarm_state, oracle_brief=brief)
            dashboard.update_market_history(df)
            
            # FORCE LOG DECISION for Cortex (CSV)
            # Only log if it's NOT just "Scanning..." to save disk/spam?
            # User wants "Cortex Updates", likely wants to see the thoughts.
            if run_ai or decision['action'] != "WAIT":
                # We log even Holds so the user sees the logic "Why Hold?"
                dashboard.log_decision(decision)

            # E. Execution Logic
            if decision['action'] in ["BUY", "SELL"]:
                # Position Sizing
                atr = df.iloc[-1]['ATR_14']
                
                # Check for Scout Protocol (Counter-Trend)
                is_scout = False
                if 'darwin_signal' in locals() and darwin_signal.get('scout_mode', False):
                    is_scout = True
                    print("⚔️ EXECUTING SCOUT PROTOCOL: Counter-Trend Entry! Validating Fractal Stops...")

                if is_scout:
                    # SCOUT LOGIC: Tight Stop at Recent Fractal, Aggressive TP (1:3) to catch the move
                    if decision['action'] == "BUY":
                        # SL below recent Fractal Low
                        sl_price = fractal_levels.get('fractal_low', current_price - atr)
                        # Sanity: If fractal is too far or invalid, use tight ATR
                        if sl_price >= current_price or (current_price - sl_price) > (3*atr):
                             sl_price = current_price - (atr * 1.0)
                             
                        risk = current_price - sl_price
                        tp_price = current_price + (risk * 3.0) # Aim for big reversal/correction
                        
                    else: # SELL
                        # SL above recent Fractal High
                        sl_price = fractal_levels.get('fractal_high', current_price + atr)
                        if sl_price <= current_price or (sl_price - current_price) > (3*atr):
                             sl_price = current_price + (atr * 1.0)
                             
                        risk = sl_price - current_price
                        tp_price = current_price - (risk * 3.0)
                
                else:
                    # STANDARD LOGIC
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
                    
                    # SCOUT SAFETY: Half Risk
                    if is_scout:
                        units = units * 0.5 
                        print(f"🛡️ Scout Risk Applied: Units HALVED to {units:.2f}")

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
