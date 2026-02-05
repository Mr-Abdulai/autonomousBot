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
# BUG FIX #12: TimeManager removed - file doesn't exist
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
    # BUG FIX #12: time_manager removed - not used
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
    # Initialize Safe Defaults once
    account_info = {
        "equity": 10000.0 if Config.BACKTEST_MODE else 0.0, # SAFETY: 0.0 for live to prevent trading on ghosts
        "balance": 10000.0 if Config.BACKTEST_MODE else 0.0,
        "profit": 0.0,
        "margin": 0.0,
        "margin_free": 10000.0 if Config.BACKTEST_MODE else 0.0,
        "name": "Sim",
        "server": "SimServer",
        "currency": "USD",
        "leverage": 100,
        "daily_pnl": 0.0,
        "total_pnl": 0.0
    }
    
    while True:
        try:
            # Refresh Account Info (Partial Update)

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
                
                # Check if news system is available (Handle 403 gracefully)
                try:
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
                except Exception as e:
                    print(f"⚠️ News Feed Error: {e}")
            
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
            
            bif_stats = mtf_analysis['mtf_stats']['BASE']
            alignment_score = mtf_analysis['alignment_score']
            
            # Phase 83: Darwinian Evolution (Update Strategies)
            darwin.update(df, latest_indicators, mtf_data)
            leader_stats = darwin.get_leaderboard()
            
            # DASHBOARD INJECTION: Map new MTF stack to Frontend Keys
            # Frontend expects: trend_d1, trend_h4, trend_m15
            # We map: 
            # D1 -> HTF2 (H4 Macro)
            # H4 -> HTF1 (M15 Mid)
            # M15 -> BASE (M5 Micro)
            
            latest_indicators['trend_d1'] = mtf_analysis['mtf_stats']['HTF2'].get('trend', 'NEUTRAL') if 'trend' in mtf_analysis['mtf_stats']['HTF2'] else "NEUTRAL" # Fallback if trend logic varies
            # Actually mtf_analysis returns 'trend' as string in 'mtf_stats'?
            # Wait, bif_brain.py analyze_mtf_regime returns 'mtf_stats': {'BASE': {'hurst':...}, ...}, "trend": "STATUS", "summary": ...
            # It DOES NOT return simple trend direction per TF in 'mtf_stats'.
            # I need to recalculate or extract them.
            # BIFBrain calculates them internally but doesn't expose them in mtf_stats dictionary values, only hurst/entropy there.
            # I'll just do a quick check here or update BIFBrain to return them.
            # QUICK CALC for Dashboard:
            def fast_trend(tf_key):
                _df = mtf_data.get(tf_key)
                if _df is None or _df.empty or len(_df) < 50: return "NEUTRAL"
                # FIX: Calculate EMA on the fly (raw data doesn't have it)
                close = _df['close'].iloc[-1]
                ema_50 = _df['close'].ewm(span=50).mean().iloc[-1]
                return "BULLISH" if close > ema_50 else "BEARISH"
            
            latest_indicators['trend_d1'] = fast_trend('HTF2')
            latest_indicators['trend_h4'] = fast_trend('HTF1')
            latest_indicators['trend_m15'] = fast_trend('BASE')

            # Enhance Market Summary for AI
            regime_tag = "UNKNOWN"
            if bif_stats['hurst'] > 0.55:
                regime_tag = "TRENDING (PERSISTENT)"
            elif bif_stats['hurst'] < 0.45:
                regime_tag = "MEAN REVERTING (CHOPPY)"
            else:
                regime_tag = "RANDOM WALK (NOISE)"
                
            if alignment_score < 0.2: # Updated threshold from -0.5 to 0.2 (Scalping) or whatever was set
                 # Actually BIFBrain now returns alignment_score.
                 pass
            
            # PHASE 6: GOLD ADVANCED INDICATOR CONFIRMATIONS
            # BUG FIX #8: Wrap in try-except to prevent crashes on bad data
            try:
                from app.ta_lib import TALib
                
                vwap = TALib.calculate_vwap(df)
                supertrend = TALib.calculate_supertrend(df, period=10, multiplier=3.0)
                rvi = TALib.calculate_rvi(df, period=14)
                
                # Store for later use in decision enhancement
                advanced_indicators = {
                    'vwap': vwap,
                    'supertrend': supertrend,
                    'rvi': rvi
                }
                
                print(f"🔍 GOLD Advanced Indicators: VWAP={vwap:.5f}, SuperTrend={supertrend['trend']} at {supertrend['level']:.5f}, RVI={rvi:.2f}")
            
            except Exception as e:
                # Graceful degradation: Use neutral defaults
                print(f"⚠️ Advanced indicators failed ({e}), using neutral defaults")
                advanced_indicators = {
                    'vwap': current_price,  # Neutral (current price)
                    'supertrend': {'trend': 'NEUTRAL', 'level': current_price, 'signal': 0},
                    'rvi': 0.0  # Neutral momentum
                }
            
            market_summary = f"{market_summary}\n\n📊 REGIME: {regime_tag}\n🧠 BIF Stats (BASE): Hurst={bif_stats['hurst']:.2f}, Entropy={bif_stats['entropy']:.2f}, Alignment={alignment_score:.2f}"
            
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
            
            # PHASE 68: MOMENTUM BOOST
            # If we just closed a trade in profit, trigger the Hot Hand mechanic
            if monitor_result.get('closed_pnl', 0.0) > 0:
                print(f"💰 PROFIT LOCKED (${monitor_result['closed_pnl']:.2f}). Triggering Momentum Boost.")
                risk_manager.register_win()
            
            # C. Determine System State & Decision
            run_ai = True
            decision = {"action": "WAIT", "confidence_score": 0.0, "reasoning_summary": "Scanning..."}
            sim_result = {} # Chronos Stats Container
            
            # --- NEWS OVERRIDE ---
            if news_signal:
                print("⚡ NEWS INTERVENTION: Skipping Technical Gates.")
                decision = news_signal
                decision['confidence_score'] = 1.0 # Max Confidence
                decision['stop_loss_atr_multiplier'] = 2.0 # Volatility Buffer
                run_ai = False # Skip Standard AI
            
            # --- SMART FILTER (CPU/API SAVER) ---
            # If Technicals are dead flat, don't even bother with Gates.
            if Config.SMART_FILTER and not news_signal and run_ai:
                 # Check volatility
                 adx = latest_indicators.get('adx', 0)
                 
                 # GOLD OPTIMIZED: Lower ADX threshold (Gold trends HARD once it starts)
                 # ADX threshold: 8 (aggressive) to 13 (passive)
                 adx_threshold = 8 + (5 * (1 - Config.EXECUTION_MODE))
                 
                 # Alignment threshold: -0.6 (passive) to -0.1 (aggressive)
                 alignment_threshold = -0.6 + (0.5 * Config.EXECUTION_MODE)
                 
                 # Only block if BOTH conditions are extreme
                 if adx < adx_threshold and alignment_score < alignment_threshold:
                     decision['reasoning_summary'] = f"Smart Filter: Market Dead (ADX {adx:.1f}<{adx_threshold:.0f}, Alignment {alignment_score:.2f}<{alignment_threshold:.2f}). Sleeping."
                     run_ai = False
                     print(f"DEBUG: Smart Filter Active (ADX {adx:.1f}, Alignment {alignment_score:.2f}). Skipping Gates.", flush=True)

            # BUG FIX #12: TimeManager removed - use Config.OVERRIDE_TIME_GUARD instead
            # Market hours check removed (TimeManager file doesn't exist)
            # User can control via OVERRIDE_TIME_GUARD=true in .env to trade 24/7
            
            run_ai = True
            
            # Gate 1: Spread Guard (Critical during News) - GOLD OPTIMIZED
            spread = latest_indicators.get('spread', 0)
            # Use Gold-specific spread tolerance (50 pts vs 20 pts for forex)
            if (run_ai or news_signal) and not risk_manager.validate_spread(spread, Config.MAX_SPREAD_POINTS):
                 decision['reasoning_summary'] = f"Spread High ({spread} > {Config.MAX_SPREAD_POINTS}). Paused."
                 run_ai = False
                 print(f"DEBUG: Gate 1 (Spread) Blocked. Spread: {spread} > {Config.MAX_SPREAD_POINTS}", flush=True)
                 if news_signal:
                     print("❌ News Trade Aborted due to Spread Spike.")
                     decision['action'] = "WAIT"

            # Gate 2: MTF Alignment Check (The Matrix)
            # IGNORE IF NEWS SIGNAL
            # Gate 2: MTF Alignment Check (The Matrix)
            # IGNORE IF NEWS SIGNAL
            # Gate 2: MTF Alignment Check (The Matrix)
            # IGNORE IF NEWS SIGNAL
            print(f"DEBUG: Checking Gate 2. alignment_score={alignment_score}, run_ai={run_ai}", flush=True)
            # SCALPING TWEAK: Relaxed alignment check. 
            # 0.0 was too strict (blocked ranging markets). -0.5 allows "Weak Conflict" / Ranging.
            if run_ai and not news_signal and alignment_score < -0.5:
                 decision['reasoning_summary'] = f"⛔ MTF MISMATCH. Score {alignment_score}. Waiting."
                 run_ai = False
                 print("DEBUG: Gate 2 Blocked (Severe Misalignment).", flush=True)
                 
            # Gate 3: Darwinian Signal (The Jury Protocol)
            # Gate 3: Darwinian Signal (The Jury Protocol)
            if run_ai:
                print("DEBUG: Entering Gate 3 (Darwin)...", flush=True)
                darwin_signal = darwin.get_consensus_signal(df, latest_indicators, mtf_data)
                print(f"DEBUG: Darwin Signal: {darwin_signal}", flush=True)
                
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

            # PHASE 77: MAX TRADES GUARD
            # User reported over-trading. We must strictly enforce the limit BEFORE calling AI.
            if len(active_trades) >= Config.MAX_OPEN_TRADES:
                print(f"🛑 MAX TRADES LIMIT HIT ({len(active_trades)}/{Config.MAX_OPEN_TRADES}). Halting new signals.")
                run_ai = False
                decision['reasoning_summary'] = f"Max Trades Reached ({len(active_trades)}/{Config.MAX_OPEN_TRADES}). Waiting for exit."
            
            # Gate 4: Project Chronos (The Oracle of Time)
            if run_ai:
                print("DEBUG: Entering Gate 4 (Chronos Simulation)...", flush=True)
                # 1. Initialize Weaver with Deep History
                weaver = ChronosWeaver(df_deep)
                
                # 2. Generate Futures (100 Paths, 10 Period Horizon)
                # Use current ATR for volatility estimation
                atr_val = latest_indicators.get('atr', latest_indicators.get('ATR_14', 0.0))
                current_vol = atr_val / current_price if current_price > 0 else 0.001
                
                features = {'price': current_price, 'atr': atr_val, 'volatility': current_vol}
                
                # Hybrid: Use Bootstrap if possible, else Monte Carlo
                futures = weaver.generate_historical_echoes(features, n_futures=50, horizon=48) # 4 Hours (was 12/1h)
                
                # 3. Simulate The Jury's Call
                # Estimate TP/SL based on Decision (TrendHawk uses 2x Risk, etc)
                # We'll use a standard test: 1 ATR Risk, 2 ATR Reward
                sim_action = darwin_signal.get('action', 'HOLD')
                
                if sim_action in ['BUY', 'SELL']:
                    sim_result = chronos_arena.run_simulation(
                        signal_type=sim_action, 
                        futures=futures, 
                        entry_price=current_price, 
                        sl_dist=atr_val * 1.5, # FIXED: Tighter SL for Simulation (was 2.5) to test accuracy
                        tp_dist=atr_val * 2.5  # FIXED: Slightly easier target (was 3.0) 
                    )
                    
                    print(f"🔮 Chronos Output: {sim_result['recommendation']} (WinRate: {sim_result['win_rate']:.2f}, Survival: {sim_result['survival_rate']:.2f})")
                    
                    if sim_result['recommendation'] == 'BLOCK':
                        decision['reasoning_summary'] = f"Chronos Veto: Low Success Probability ({sim_result['win_rate']:.2f})"
                        run_ai = False
                        print("DEBUG: Gate 4 (Chronos) Blocked.", flush=True)
                    else:
                        print("DEBUG: Gate 4 Passed. Simulation confirmed.", flush=True)
                        market_summary += f"\n[GATE 4 PASSED] [SIMULATION VERIFIED] Chronos Win Rate: {sim_result['win_rate']:.2f} (Survivor: {sim_result['survival_rate']:.2f})"
                        
                        # PHASE 5A: Store Chronos result for position scaling
                        decision['chronos_result'] = sim_result
                else:
                    print("DEBUG: Chronos skipped (No Directional Signal).", flush=True)

            # D. AI Strategy Layer (Groq)
            analyzed_decision = {}  # BUG FIX #3: Initialize to prevent undefined variable crash
            
            if run_ai:
                print("DEBUG: Calling Groq Strategist...", flush=True)
                analyzed_decision = ai_strategist.get_trade_decision(market_summary, "")
                print(f"DEBUG: Groq Response: {analyzed_decision}", flush=True)
                # BUG FIX #1: PHASE 6 GOLD ENTRY CONFIRMATION - MOVED HERE
                # Boost confidence with advanced indicators (VWAP, SuperTrend, RVI)
                if analyzed_decision['action'] in ['BUY', 'SELL']:
                    confidence_boost = 0.0
                    confirmations = []
                    
                    # VWAP Confirmation (Institutional level)
                    if analyzed_decision['action'] == 'BUY' and current_price > advanced_indicators['vwap']:
                        confidence_boost += 0.15
                        confirmations.append("VWAP Support (Institutions Buying)")
                        print(f"✓ GOLD Confirmation #1: Price above VWAP ({advanced_indicators['vwap']:.5f})")
                    elif analyzed_decision['action'] == 'SELL' and current_price < advanced_indicators['vwap']:
                        confidence_boost += 0.15
                        confirmations.append("VWAP Resistance (Institutions Selling)")
                        print(f"✓ GOLD Confirmation #1: Price below VWAP ({advanced_indicators['vwap']:.5f})")
                    
                    # SuperTrend Confirmation (Trend alignment)
                    st_trend = advanced_indicators['supertrend']['trend']
                    if (analyzed_decision['action'] == 'BUY' and st_trend == 'UP') or \
                       (analyzed_decision['action'] == 'SELL' and st_trend == 'DOWN'):
                        confidence_boost += 0.12
                        confirmations.append(f"SuperTrend {st_trend}")
                        print(f"✓ GOLD Confirmation #2: SuperTrend aligned ({st_trend} at {advanced_indicators['supertrend']['level']:.5f})")
                    
                    # RVI Momentum Confirmation
                    rvi_val = advanced_indicators['rvi']
                    if (analyzed_decision['action'] == 'BUY' and rvi_val > 0.3) or \
                       (analyzed_decision['action'] == 'SELL' and rvi_val < -0.3):
                        confidence_boost += 0.10
                        confirmations.append(f"Strong RVI ({rvi_val:.2f})")
                        print(f"✓ GOLD Confirmation #3: RVI momentum aligned ({rvi_val:.2f})")
                    
                    # Apply boost
                    if confidence_boost > 0:
                        original_confidence = analyzed_decision.get('confidence_score', 0.5)
                        analyzed_decision['confidence_score'] = min(original_confidence + confidence_boost, 0.95)  # Cap at 0.95
                        analyzed_decision['reasoning_summary'] = f"{analyzed_decision.get('reasoning_summary', '')} | GOLD Confirmations: {', '.join(confirmations)}"
                        print(f"💎 GOLD Quality Boost: {original_confidence:.2f} → {analyzed_decision['confidence_score']:.2f} (+{confidence_boost:.2f}) [{len(confirmations)} confirmations]")

                decision = risk_manager.validate_signal(analyzed_decision)
                
                # [MOVED UP] -> Inserted earlier
                
            # Log State
            swarm_state = darwin.get_swarm_state()
            
            # ORACLE BRIEFING
            brief = oracle.generate_brief(
                market_data=latest_indicators, # FIX: Pass Dict, not Str
                regime={"trend": regime_tag, "summary": bif_context},
                leader_name=darwin.leader.name,
                active_trades=active_trades
            )
            
            dashboard.update_system_state(account_info, active_trades, latest_indicators, decision, bif_stats=bif_stats, swarm_state=swarm_state, oracle_brief=brief, chronos_stats=sim_result)
            dashboard.update_market_history(df)
            
            # FORCE LOG DECISION for Cortex (CSV)
            if True: # DEBUG: FORCE LOGGING ALL STATES TO DIAGNOSE SILENT FAILURES
                print(f"DEBUG: Logging decision: {decision['action']}", flush=True)
                try:
                    dashboard.log_decision(decision)
                    print("DEBUG: Logged to CSV.", flush=True)
                except Exception as e:
                    print(f"DEBUG: Failed to log decision: {e}", flush=True)
                
            # E. Execution Logic
            if decision['action'] in ["BUY", "SELL"]:
                # Position Sizing
                atr = df.iloc[-1]['ATR_14']
                
                # BUG FIX #9: Removed scout mode dead code ('darwin_signal' never defined)
                # Scout protocol logic removed (lines 432-458) - was never triggered
                
                # STANDARD STOP LOSS & TAKE PROFIT LOGIC
                sl_mult = decision.get("stop_loss_atr_multiplier", 2.5)  # GOLD: Default 2.5 (vs 1.5 forex)
                
                # PHASE 5A + GOLD: ADAPTIVE STOP LOSS based on Market Regime
                # Get BIF metrics from MTF data
                mtf_analysis = mtf_data.get('analysis', {})
                mtf_stats = mtf_analysis.get('mtf_stats', {})
                # FIX: Use BASE (M5) instead of hardcoded M15
                base_stats = mtf_stats.get('BASE', {})
                hurst = base_stats.get('hurst', 0.5)
                entropy = base_stats.get('entropy', 0.7)
                
                # GOLD OPTIMIZED: Wider adjustments for volatility
                # Trending Market (High Hurst): MUCH wider stops for Gold's explosive moves
                if hurst > 0.6:
                    sl_mult *= 1.5  # +50% wider in strong trends (vs 1.3x for forex)
                    print(f"📊 Adaptive SL (GOLD): Trending market (H={hurst:.2f}), widening stops by 50%")
                # Ranging Market (Low Hurst): Moderate tightening (Gold ranges are still volatile)
                elif hurst < 0.4:
                    sl_mult *= 0.9  # -10% tighter in ranging (vs 0.8x for forex, Gold needs room)
                    print(f"📊 Adaptive SL (GOLD): Ranging market (H={hurst:.2f}), tightening stops by 10%")
                
                # Low Entropy = More Certainty = Slightly tighter
                if entropy < 0.5:
                    sl_mult *= 0.95  # -5% in clear markets (vs 0.9x for forex)
                    print(f"📊 Adaptive SL (GOLD): Low entropy ({entropy:.2f}), tightening by 5%")
                
                if decision['action'] == "BUY":
                    sl_price = current_price - (atr * sl_mult)
                    tp_price = current_price + ((current_price - sl_price) * 2.0)
                else:
                    sl_price = current_price + (atr * sl_mult)
                    tp_price = current_price - ((sl_price - current_price) * 2.0)

                risk_distance = abs(current_price - sl_price)
                
                # BUG FIX #2: KELLY CRITERION POSITION SIZING
                # Use Kelly when we have sufficient trading history (30+ trades)
                # Otherwise fallback to fixed risk
                
                leader_stats = darwin.leader
                has_history = len(leader_stats.trade_history) >= 30
                
                if has_history:
                    # Calculate stats from leader's trade history
                    wins = [t['pnl'] for t in leader_stats.trade_history if t['pnl'] > 0]
                    losses = [abs(t['pnl']) for t in leader_stats.trade_history if t['pnl'] < 0]
                    
                    win_rate = len(wins) / len(leader_stats.trade_history) if leader_stats.trade_history else 0.5
                    avg_win = sum(wins) / len(wins) if wins else 1.0
                    avg_loss = sum(losses) / len(losses) if losses else 1.0
                    
                    # Use Kelly Criterion
                    units = risk_manager.calculate_kelly_position(
                        win_rate=win_rate,
                        avg_win=avg_win,
                        avg_loss=avg_loss,
                        equity=account_info["equity"],
                        current_price=current_price,
                        sl_price=sl_price
                    )
                    print(f"📊 KELLY SIZING: WR={win_rate:.1%}, R:R={avg_win/avg_loss:.2f}, Units={units:.2f}")
                else:
                    # Fallback to fixed risk (not enough history)
                    units = risk_manager.calculate_position_size(account_info["equity"], current_price, sl_price)
                    print(f"📊 FIXED RISK: {len(leader_stats.trade_history)} trades (need 30 for Kelly)")
                
                # PHASE 5A: CHRONOS CONFIDENCE WEIGHTING
                # Scale position size based on Chronos simulation results
                if 'chronos_result' in decision:
                    chronos_winrate = decision['chronos_result'].get('win_rate', 0.5)
                    chronos_survival = decision['chronos_result'].get('survival_rate', 0.7)
                    
                    # Scale position: 40% WR = 0.7x, 50% = 1.0x, 70% = 1.3x, 80% = 1.5x
                    chronos_multiplier = 0.5 + (chronos_winrate * 1.0)
                    
                    # Cap at reasonable bounds
                    chronos_multiplier = max(0.5, min(1.5, chronos_multiplier))
                    
                    units *= chronos_multiplier
                    print(f"🔮 Chronos Scaling: {chronos_multiplier:.2f}x (WinRate: {chronos_winrate:.1%}, Survival: {chronos_survival:.1%})")
                else:
                    print("🔮 Chronos: No simulation data, using base position size")

                # BUG FIX #9: Removed scout safety halving (scout mode removed)

                execution_info = None
                if units > 0:
                        execution_info = executor.execute_trade(decision['action'], sl_price, tp_price, units)
                
                # Log decision with execution info (if any)
                # Ensure we log even if no trade was taken (HOLD/WAIT), but if taken, include details
                logger.log_decision(decision, execution_info)
            
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
