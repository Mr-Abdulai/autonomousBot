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
                "balance": 10000.0,
                "profit": 0.0,
                "margin": 0.0,
                "margin_free": 10000.0,
                "name": "Sim",
                "server": "SimServer",
                "currency": "USD",
                "leverage": 100,
                "daily_pnl": 0.0,
                "total_pnl": 0.0
            }
            if not Config.BACKTEST_MODE and mt5.initialize():
                acc = mt5.account_info()
                if acc:
                   account_info['equity'] = acc.equity
                   account_info['balance'] = acc.balance
                   account_info['profit'] = acc.profit
                   account_info['margin'] = acc.margin
                   account_info['margin_free'] = acc.margin_free
                   account_info['name'] = acc.name
                   account_info['server'] = acc.server
                   account_info['currency'] = acc.currency
                   account_info['leverage'] = acc.leverage
                   
                   # --- CALCULATE PnL from History ---
                   try:
                       now = datetime.now()
                       # Daily (Since Midnight)
                       midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
                       daily_deals = mt5.history_deals_get(midnight, now)
                       
                       if daily_deals and len(daily_deals) > 0:
                           # Net Profit = Profit + Swap + Commission + Fee
                           account_info['daily_pnl'] = sum([d.profit + d.swap + d.commission + d.fee for d in daily_deals])
                       
                       # Total (All Time - Safer Start Date)
                       # 1970 can cause overflow in some broker bridges. Using 2010.
                       start_date = datetime(2010, 1, 1)
                       all_deals = mt5.history_deals_get(start_date, now)
                       
                       if all_deals and len(all_deals) > 0:
                           # FILTER OUT DEPOSITS (Type 2 = Balance)
                           # We only want Trading Profit (Buy/Sell) + Fees
                           trading_deals = [d for d in all_deals if d.type != mt5.DEAL_TYPE_BALANCE]
                           account_info['total_pnl'] = sum([d.profit + d.swap + d.commission + d.fee for d in trading_deals])
                   except Exception as e:
                       print(f"PnL Calc Warning: {e}") # Log but don't crash loop

            # One-time Sync for Risk Manager (Prevents "95% Daily Loss" on restart)
            if 'risk_synced' not in locals():
                 risk_manager.sync_start_balance(account_info['equity'])
                 locals()['risk_synced'] = True
            
            risk_manager.update_account_state(account_info['equity'])
            
            # --- NEWS RADAR (Phase 60) ---
            # Check for News Triggers every 5 minutes (to avoid IP bans)
            if 'last_news_check' not in locals(): locals()['last_news_check'] = datetime.now() - timedelta(minutes=10)
            
            news_signal = None
            if (datetime.now() - locals()['last_news_check']).total_seconds() > 300:
                print("📡 Scanning News Radar...")
                locals()['last_news_check'] = datetime.now()
                
                # We need to access the Harvester directly or add a method to Sensor
                # Sensor checks news in get_market_summary but doesn't return the event object.
                # Let's access sensor.news directly.
                event = sensor.news.fetch_latest_trigger()
                
                if event:
                    print(f"🚨 NEWS TRIGGER DETECTED: {event['currency']} {event['event']} (Act: {event['actual']} vs Fcst: {event['forecast']})")
                    # Quick Trend Check for Context
                    trend_m15 = sensor.get_trend_data(Config.TIMEFRAME)
                    
                    # AI Analysis
                    news_decision = ai_strategist.analyze_news_impact(event, trend_m15)
                    
                    if news_decision['action'] in ['BUY', 'SELL']:
                        print(f"🗞️ NEWS TRADING SIGNAL: {news_decision['action']} ({news_decision['reasoning']})")
                        news_signal = news_decision
                        
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
