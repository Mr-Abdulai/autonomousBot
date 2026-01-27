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

def main():
    print("=== Hybrid Neuro-Symbolic Trading System Starting ===")
    
    # 1. Validation
    try:
        Config.validate()
    except EnvironmentError as e:
        print(f"CRITICAL: {e}")
        sys.exit(1)

    # 2. Module Initialization
    sensor = MarketSensor()
    strategist = GroqStrategist()
    risk_manager = IronCladRiskManager()
    executor = ExecutionEngine()
    logger = DashboardLogger()
    logger = DashboardLogger()
    analyzer = PerformanceAnalyzer() # Memory Component
    time_manager = TimeManager()
    brain = BIFBrain() # Phase 69: The Alpha Brain
    
    # 3. Connection Check (Early Fail)
    if not sensor.initialize():
        print("CRITICAL: Failed to connect to MT5 for data feed. Exiting.")
        sys.exit(1)
        
    # SYNC SYMBOLS: Ensure Executor uses the auto-resolved name (e.g. XAUUSDm)
    executor.symbol = sensor.symbol
    Config.SYMBOL = sensor.symbol
    print(f"System Initialized. Symbol: {Config.SYMBOL}, Timeframe: {Config.TIMEFRAME}")
    print("Entering Main Loop...")

    while True:
        try:
            # 1. Gather Rich Account Info
            account_info = {
                "equity": 10000.0,
                "balance": 10000.0,
                "leverage": 1,
                "profit": 0.0,
                "margin": 0.0,
                "margin_free": 10000.0,
                "name": "Mock Account",
                "server": "Mock Server",
                "currency": "USD"
            }
            
            if not Config.BACKTEST_MODE and mt5.initialize():
                acc = mt5.account_info()
                if acc:
                    account_info.update({
                        "equity": acc.equity,
                        "balance": acc.balance,
                        "leverage": acc.leverage,
                        "profit": acc.profit,
                        "margin": acc.margin,
                        "margin_free": acc.margin_free,
                        "name": acc.name,
                        "server": acc.server,
                        "currency": acc.currency
                    })
                print(f"Updated Account Info from LIVE MT5: {account_info['name']} (${account_info['balance']})")
            else:
                print(f"Using MOCK Account Data (Backtest Mode): ${account_info['balance']}")

            # Calculate Historical PnL Metrics
            daily_pnl = 0.0
            total_pnl = 0.0
            last_ai_scan = 0 # Initialize timer
            
            
            if not Config.BACKTEST_MODE and mt5.initialize():
                try:
                    # Time alignment - Use Float Timestamps for max compatibility
                    utc_now = datetime.now(timezone.utc)
                    to_date = utc_now + timedelta(hours=24) 
                    
                    # Daily
                    day_start = datetime(utc_now.year, utc_now.month, utc_now.day, tzinfo=timezone.utc)
                    deals_day = mt5.history_deals_get(day_start.timestamp(), to_date.timestamp())
                    
                    if deals_day is not None and len(deals_day) > 0:
                        daily_pnl = sum([d.profit + d.swap + d.commission for d in deals_day if d.type != mt5.DEAL_TYPE_BALANCE and d.type != mt5.DEAL_TYPE_CREDIT])
                    
                    # Total (All Time: 2000-01-01 UTC)
                    from_date = datetime(2015, 1, 1, tzinfo=timezone.utc) # 2015 is safe
                    deals_all = mt5.history_deals_get(from_date.timestamp(), to_date.timestamp())
                    
                    if deals_all is not None and len(deals_all) > 0:
                         total_pnl = sum([d.profit + d.swap + d.commission for d in deals_all if d.type != mt5.DEAL_TYPE_BALANCE and d.type != mt5.DEAL_TYPE_CREDIT])
                         print(f"PnL Scan: Found {len(deals_all)} hist deals. Total PnL: {total_pnl:.2f}")
                    else:
                         # Retry with older date if 0 found? Or just log.
                         err = mt5.last_error()
                         print(f"PnL Scan Warning: 0 deals. MT5 Err: {err}. Args: {from_date} to {to_date}")
                         
                except Exception as e:
                    print(f"PnL Calc Error: {e}")
            
            account_info['daily_pnl'] = daily_pnl
            account_info['total_pnl'] = total_pnl
            
            # Initialize BIF Stats container
            bif_stats = {}

            # Phase 68: Update Risk Shield with latest Equity 
            # (Allows dynamic sizing & circuit breaker)
            risk_manager.update_account_state(account_info['equity'])

            # A. Get Current Market Data
            try:
                df = sensor.get_market_data()
                current_price = df.iloc[-1]['close']
                market_summary = sensor.get_market_summary()
                latest_indicators = sensor.get_latest_indicators()
                fractal_levels = sensor.get_latest_fractal_levels(df) # Phase 81
                
                # Phase 82: The Matrix (Multi-Timeframe Regime)
                mtf_data = sensor.fetch_mtf_data()
                mtf_analysis = brain.analyze_mtf_regime(mtf_data)
                
                bif_stats = mtf_analysis['mtf_stats']['M15'] # Backwards compat for vars below
                alignment_score = mtf_analysis['alignment_score']
                
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
"""
                market_summary += bif_context
                print(f"🧠 BIF Matrix: Score {alignment_score} | {mtf_analysis['summary']}")
            except Exception as e:
                print(f"Data Fetch Error: {e}. Retrying in 60s...")
                time.sleep(60)
                continue
                
            # B. Check for active trades & Manage them
            atr_val = latest_indicators.get('atr', latest_indicators.get('ATR_14', 0.0))
            monitor_result = executor.monitor_open_trades(current_price, atr=atr_val, fractal_levels=fractal_levels)
            active_trades = monitor_result['trades'] # List of dicts
            
            # C. Determine System State & Decision
            # Gate 0: MTF Alignment Check (The Matrix)
            if alignment_score < 0:
                 # If Score is negative, H1 is fighting M15. We Force Wait.
                 decision = {
                     "action": "HOLD",
                     "confidence_score": 0.0,
                     "reasoning_summary": f"⛔ MTF MISMATCH. M15 wants to trade but H1/H4 disagree (Score {alignment_score}). Waiting for alignment.",
                     "contract_symbol": Config.SYMBOL
                 }
                 # Skip AI call
                 run_ai = False
            else:
                 run_ai = True
            
            # C. Determine System State & Decision
            can_execute_new = False
            trade_to_cycle = None # Ticket to close if we need room
            decision = {
                "action": "WAIT", 
                "confidence_score": 0.0, 
                "reasoning_summary": "Scanning markets..."
            }
            
            if active_trades:
                # We have open positions
                decision["action"] = "MANAGING"
                stacking_msg = ""
                managed_msg = ""
                
                if monitor_result.get('managed_count', 0) > 0:
                   managed_msg = f"⚡ UPDATED {monitor_result['managed_count']} STOPS. "
                   
                # Logic Gate for Pyramiding & Cycling
                if len(active_trades) < Config.MAX_OPEN_TRADES:
                    if risk_manager.check_stacking_safety(active_trades):
                        can_execute_new = True
                        stacking_msg = "Stacking Allowed (Scale-In). "
                    else:
                        stacking_msg = "Holding (Wait for B.E. before Stacking). "
                else:
                    # MAX TRADES REACHED - Check Cycling
                    cycle_res = executor.check_cycling_condition(active_trades, current_price)
                    if cycle_res['can_cycle']:
                         can_execute_new = True
                         trade_to_cycle = cycle_res['trade_to_close']
                         stacking_msg = f"♻️ CYCLING MODE ACTIVE (Will close T{trade_to_cycle} if new trade found). "
                    else:
                        stacking_msg = "Max Trades Reached & Targets Not Met. "
                    
                decision["reasoning_summary"] = f"{managed_msg}Managing {len(active_trades)} positions. {stacking_msg}"
                
            else:
                # No trades open
                can_execute_new = True

            # D. GATE 1: TIME & SESSION CHECK (Phase 67)
            # We strictly enforce "Kill Zones" (Night/Asia) to prevent low-liquidity trading.
            if not time_manager.is_market_open():
                session_status = time_manager.get_session_status()
                if can_execute_new:
                    print(f"💤 TIME GUARD: Market Closed/Kill Zone ({session_status}). Sleeping.")
                    decision["reasoning_summary"] = f"💤 {session_status}. Waiting for London."
                can_execute_new = False # Force Block
                
            # E. VALIDATE SPREAD (News/Volatility Guard)
            current_spread = latest_indicators.get('spread', 0)
            if not risk_manager.validate_spread(current_spread):
                if can_execute_new: 
                    print(f"⚠️ SPREAD GUARD: Spread {current_spread} > 20 points. BLOCKING new entries.")
                    decision['reasoning_summary'] = f"SPREAD HIGH ({current_spread}). Paused."
                can_execute_new = False
                if monitor_result['closed_pnl'] != 0:
                     decision["reasoning_summary"] = f"Last Trade PnL: {monitor_result['closed_pnl']:.2f}. Searching..."
                
            # E. PHASE 60: SEMANTIC NEWS CHECK (Reactive)
            # Only check if we are not already busy managing max trades
            # But News might warrant an emergency entry overrides? For now, respect max trades.
            if len(active_trades) < Config.MAX_OPEN_TRADES:
                news_trigger = sensor.news.fetch_latest_trigger()
                
                # NEWS SPREAD GUARD: News spikes spread. Allow up to 50 points (5.0 pips).
                # If spread is > 50, it's too dangerous even for news.
                if news_trigger and current_spread <= 50:
                    print(f"🚨 NEWS REACTION MODE: {news_trigger['event']} (Actual: {news_trigger['actual']})")
                    
                    # Current Trend Context
                    trend_txt = latest_indicators.get('trend_m15', 'Unknown')
                    
                    # Ask AI
                    print("🧠 Analyzing Semantic Impact...")
                    ai_response = strategist.analyze_news_impact(news_trigger, trend_txt)
                    
                    decision = ai_response
                    decision['reasoning_summary'] = f"NEWS EVENT: {decision.get('reasoning', '')}"
                    
                    # Execute Immediate
                    if decision['action'] in ["BUY", "SELL"]:
                         print(f"🚀 EXECUTING NEWS TRADE: {decision['action']}")
                         order_result = executor.execute_trade(
                            decision['action'], 
                            current_price, 
                            sl_atr_mult=1.5, # Tighter SL for volatility? Or Wide? 
                            # Let's stick to standard 1.5, volatility will make ATR huge anyway.
                            risk_per_trade=0.02
                         )
                         if order_result:
                             print(f"✅ News Trade Open: {order_result}")
                             # Sleep to avoid double entry on same news ping (News stays 'latest' for 15m)
                             # In reality, fetch_latest_trigger clears cache or we track ID.
                             # For now, simplistic sleep or verify 'active' check.
                             # Better: simple continue prevents Technical trade.
                    
                    # Skip Technical Analysis
                    can_execute_new = False 
                    
            # F. Standard AI Analysis (If no News Trigger)
            if can_execute_new:
                 # --- SMART WAKE-UP FILTER ---
                run_ai = True
                if Config.SMART_FILTER:
                    rsi = latest_indicators.get('rsi', 50)
                    bb_upper = latest_indicators.get('bb_upper', 999999)
                    bb_lower = latest_indicators.get('bb_lower', 0)
                    
                    is_exciting = (rsi < 35 or rsi > 65) or \
                                  (current_price >= bb_upper * 0.9995) or \
                                  (current_price <= bb_lower * 1.0005)
                    
                    # Macro Trend Filter (SMC)
                    trend_d1 = latest_indicators.get('trend_d1', "Unknown")
                    trend_h4 = latest_indicators.get('trend_h4', "Unknown")
                    trend_m15 = latest_indicators.get('trend_m15', "Unknown")
                    
                    # Trend Direction Booleans
                    d1_bull = "Bullish" in trend_d1
                    d1_bear = "Bearish" in trend_d1
                    h4_bull = "Bullish" in trend_h4
                    h4_bear = "Bearish" in trend_h4
                    m15_bull = "Bullish" in trend_m15
                    m15_bear = "Bearish" in trend_m15
                    
                    # 3-Stage Alignment Logic
                    # Filter passes if H4 and M15 align (Minimum requirement)
                    aligned_bull = h4_bull and m15_bull
                    aligned_bear = h4_bear and m15_bear
                    
                    trends_aligned = aligned_bull or aligned_bear
                    
                    # Sleep if: Trends Conflict (User Request: RSI only for confirmation)
                    should_sleep = not trends_aligned
                                  
                    if should_sleep and not active_trades: # Only sleep if no trades to manage
                        print(f"💤 Smart Filter: Trends Conflict (H4={trend_h4}, M15={trend_m15}). AI Sleeping.")
                        decision = {
                            "action": "HOLD",
                            "confidence_score": 0.0,
                            "reasoning_summary": f"💤 Cost Saver Mode: Trends Conflict (H4/M15)."
                        }
                        run_ai = False

                if run_ai:
                    # COOLDOWN CHECK: Prevent AI spam. Only run every 5 mins (or Config interval)
                    # Unless we have significant News (handled separately above)
                    time_since_last = time.time() - last_ai_scan
                    if time_since_last < Config.AI_SCAN_INTERVAL:
                        remaining = int(Config.AI_SCAN_INTERVAL - time_since_last)
                        decision["reasoning_summary"] = f"⏳ Cooldown: Waiting {remaining}s for next scan..."
                        run_ai = False
                    else:
                        # 0. CHAOS GUARD (Phase 70)
                        # If Entropy is too high (Pure Noise), do not trade.
                        current_entropy = bif_stats.get('entropy', 0.5)
                        if current_entropy > 0.95:
                             print(f"💤 CHAOS GUARD: Entropy {current_entropy:.2f} > 0.95. Market is Random Noise. Sleeping.")
                             decision["reasoning_summary"] = f"💤 Chaos Guard: Market is too random (Entropy {current_entropy:.2f})."
                             run_ai = False

                        # 100% EFFICIENCY: ADVANCED GATEKEEPER 5.0 (FRACTAL GEOMETRY)
                        
                        # A. DETECT STRUCTURE (FRACTALS)
                        # Replaced Candlesticks with Bill Williams Fractals
                        fractal_signal, fractal_level = sensor.get_fractal_structure(df)
                        has_fractal_event = fractal_signal != "NONE"
                        
                        in_ob_zone = "[INSIDE_ZONE (READY)]" in market_summary
                        has_price_structure = has_fractal_event or in_ob_zone
                        
                        # B. FETCH METRICS
                        hurst = bif_stats.get('hurst', 0.5)
                        is_trending = hurst > 0.55
                        is_ranging = hurst < 0.45
                        is_confluent, conf_reason = sensor.check_technical_confluence()
                        
                        is_valid_setup = False
                        setup_reason = ""

                        # --- LOGIC BRANCHING ---
                        # 1. Structure Check (The Hard Filter)
                        if not has_price_structure:
                             # IF Indicators are aligned ONLY, we BLOCK IT.
                             if is_confluent:
                                 print(f"🛑 BLOCKED: Good Indicators ({conf_reason}) but NO STRUCTURE (No Fractal Break/OB).")
                             else:
                                 pass 
                        
                        else:
                            # Scenario A: SMC (The Golden Setup)
                            if in_ob_zone:
                                is_valid_setup = True
                                setup_reason = "[SMC ORDER BLOCK]"
                            
                            # Scenario B: Trend Regime (Fractal Breakout)
                            elif is_trending and has_fractal_event:
                                if is_confluent:
                                    if fractal_signal == "BREAK_UP" and "BULLISH" in conf_reason:
                                         is_valid_setup = True
                                         setup_reason = f"[TREND BREAKOUT] Fractal Break {fractal_level} + {conf_reason}"
                                    elif fractal_signal == "BREAK_DOWN" and "BEARISH" in conf_reason:
                                         is_valid_setup = True
                                         setup_reason = f"[TREND BREAKOUT] Fractal Break {fractal_level} + {conf_reason}"
                                    else:
                                        print(f"⚠️ Fractal {fractal_signal} contradicts Indicators ({conf_reason}). Waiting.")
                                else:
                                    print(f"⚠️ Fractal Break ({fractal_signal}) but Indicators not ready. Waiting.")
                            
                            # Scenario C: Range Regime (Block Breakouts)
                            elif is_ranging and has_fractal_event:
                                 print(f"🛑 BLOCKED: Fractal Breakout ({fractal_signal}) in Range Regime (H={hurst:.2f}). Waiting for Mean Reversion.")

                        # Smart Filter Enforcer
                        if Config.SMART_FILTER and not is_valid_setup:
                            if not is_exciting: 
                                 current_sig = fractal_signal if has_fractal_event else "None"
                                 print(f"💤 Gatekeeper: Waiting for valid Structure. (Fractal: {current_sig}).")
                                 decision["reasoning_summary"] = f"💤 Gatekeeper: No Setup. Regime={ 'Trend' if is_trending else 'Range' }. Struct={current_sig}."
                                 run_ai = False
                                 last_ai_scan = time.time() 
                        
                        if is_valid_setup and run_ai:
                             # Inject Setup Reason into AI Context
                             market_summary += f"\n[GATE 4 PASSED]: {setup_reason}"
                        
                        if run_ai:
                            last_ai_scan = time.time() # Reset timer
                
                if run_ai:
                    print("\n--- Looking for Setup ---")
                    print(f"Market Context: {market_summary.split('Timestamp')[0].replace(chr(10), ' | ')}") 
                    
                    perf_summary = analyzer.get_performance_summary()
                    print(f"Self-Reflection: {perf_summary.split('Recency')[0]}...") 
                    
                    # Get AI Decision
                    ai_decision = strategist.get_trade_decision(market_summary, perf_summary)
                    print(f"AI Decision: {ai_decision['action']} (Conf: {ai_decision['confidence_score']})")

                    # Log the Raw Decision to CSV
                    logger.log_decision(ai_decision, {}, pnl=0.0)

                    # Risk Manager Validation
                    decision = risk_manager.validate_signal(ai_decision)
                    # Merge reasoning if valid
                    if decision['action'] != "HOLD":
                        decision['reasoning_summary'] = ai_decision.get('reasoning_summary', 'Signal Validated')
            
            # UPDATE DASHBOARD (Now that we have fresh decision & market data)
            logger.update_system_state(account_info, active_trades, latest_indicators, decision, bif_stats=bif_stats)
            logger.update_market_history(df)

            # E. Execution Logic (Only if AI triggered a NEW signal)
            # We already handled management in step B
            if decision['action'] in ["BUY", "SELL"]:
                
                # 1. Handle Cycling (Close old trade first if needed)
                if trade_to_cycle:
                    print(f"♻️ Executing Cycle Close for Ticket {trade_to_cycle}...")
                    executor.close_trade(trade_to_cycle)

                # 2. Calculate Trade Parameters for NEW Trade
                atr = df.iloc[-1]['ATR_14']
                sl_mult = decision.get("stop_loss_atr_multiplier", 1.5)
                
                if decision['action'] == "BUY":
                    sl_price = current_price - (atr * sl_mult)
                    risk_distance = current_price - sl_price
                    tp_price = current_price + (risk_distance * 2.0)
                else: # SELL
                    sl_price = current_price + (atr * sl_mult)
                    risk_distance = sl_price - current_price
                    tp_price = current_price - (risk_distance * 2.0)

                if risk_distance > 0:
                     # Calculate Position Size using REAL Equity
                    units = risk_manager.calculate_position_size(account_info["equity"], current_price, sl_price)
                    
                    if units > 0:
                        print(f"Initiating {decision['action']}... Units: {units:.2f}")
                        executor.execute_trade(decision['action'], sl_price, tp_price, units)
            
            # Wait for next tick
            # If managing, update faster (5s). If sleeping/flat, 60s.
            sleep_time = 5 if active_trades else 60
            time.sleep(sleep_time)

        except KeyboardInterrupt:
            print("Shutdown requested by user.")
            break
        except Exception as e:
            print(f"Unexpected Main Loop Error: {e}")
            time.sleep(60)

if __name__ == "__main__":
    main()
