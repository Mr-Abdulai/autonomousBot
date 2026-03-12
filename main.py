import time
import sys
from datetime import datetime, timedelta, timezone
import MetaTrader5 as mt5
import pandas as pd
import warnings
# Suppress noisy HMM warnings
warnings.filterwarnings("ignore", message="Degenerate mixture covariance")
warnings.filterwarnings("ignore", category=FutureWarning)
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
                   account_info['login'] = acc.login # Unique Account ID for Log Separation
                   
                   # --- CALCULATE PnL from History ---
                   try:
                       now = datetime.now()
                       # Daily (Since Midnight)
                       midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
                       daily_deals = mt5.history_deals_get(midnight, now)
                       
                       if daily_deals and len(daily_deals) > 0:
                           # Net Profit = Profit + Swap + Commission + Fee
                           # FILTER OUT DEPOSITS (Type 2 = Balance)
                           daily_trading = [d for d in daily_deals if d.type != mt5.DEAL_TYPE_BALANCE]
                           account_info['daily_pnl'] = sum([d.profit + d.swap + d.commission + d.fee for d in daily_trading])
                       
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

            # --- NEWS RADAR (Phase 60 & Ultimate Gold Update) ---
            # Check for News Triggers every 5 minutes (to avoid IP bans)
            if 'last_news_check' not in locals(): locals()['last_news_check'] = datetime.now() - timedelta(minutes=10)
            
            # Default to False
            if 'latest_indicators' not in locals(): latest_indicators = {}
            latest_indicators['news_event_active'] = False
            
            news_signal = None
            if (datetime.now() - locals()['last_news_check']).total_seconds() > 300:
                print("📡 Scanning News Radar...")
                locals()['last_news_check'] = datetime.now()
                
                # Check if news system is available (Handle 403 gracefully)
                try:
                    event = sensor.news.fetch_latest_trigger()
                    
                    if event:
                        print(f"🚨 NEWS TRIGGER DETECTED: {event['currency']} {event['event']} (Act: {event['actual']} vs Fcst: {event['forecast']})")
                        # ULTIMATE GOLD FIX: Instead of relying on external Groq AI to randomly guess direction,
                        # we trigger the internal NewsArbitrage Volatility Breakout module.
                        latest_indicators['news_event_active'] = True
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
            mtf_data['analysis']['trend'] = mtf_analysis['trend'] # FIX: Inject Trend for Boost
            
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
                
            # --- ULTIMATE GOLD STRATEGY 3: THE PYRAMIDING PROTOCOL ---
            # Max Pyramid instances allowed at once (so we don't scale infinitely)
            MAX_PYRAMID_TRADES = 2
            current_pyramids = len([t for t in active_trades if t.get('is_pyramid', False)])
            
            if current_pyramids < MAX_PYRAMID_TRADES:
                pyramid_check = executor.check_pyramiding_condition(active_trades, current_price)
                if pyramid_check['can_pyramid'] and pyramid_check['base_trade']:
                    base_trade = pyramid_check['base_trade']
                    p_action = pyramid_check['action_to_take']
                    base_ticket = base_trade['ticket']
                    
                    print(f"📈 PYRAMID PROTOCOL ACTIVATED: Trade {base_ticket} is deep in profit & Risk-Free. Scaling in with {p_action}!")
                    
                    # Logic: We open a new trade with HALF the size of the base trade to keep risk contained
                    base_volume = base_trade.get('volume', 0.01)
                    p_volume = max(round(base_volume * 0.5, 2), 0.01)
                    
                    # Target the same Take Profit as the base trade
                    p_tp = base_trade.get('tp')
                    
                    # Tighter SL for the pyramid trade (below recent structure)
                    # We'll use a standard ATR calculation for safety
                    p_sl_mult = 1.0 # Tighter than normal
                    if p_action == "BUY":
                        p_sl = current_price - (atr_val * p_sl_mult)
                    else:
                        p_sl = current_price + (atr_val * p_sl_mult)
                        
                    # Execute the Pyramid Trade
                    db_pyramid = executor.execute_trade(p_action, p_sl, p_tp, p_volume)
                    
                    if db_pyramid:
                        # Mark the base trade so we don't pyramid off it again
                        executor._mark_trade_pyramided(base_ticket)
                        # Mark the new trade as a pyramid instance
                        db_pyramid['is_pyramid'] = True 
                        # Save the updated tags to state
                        executor.save_state(executor.load_state() + [db_pyramid]) # Need to merge correctly, but executor already saved db_pyramid. So just re-save.
                        
                        # Correct persistence update:
                        current_state = executor.load_state()
                        for t in current_state:
                            if t['ticket'] == base_ticket:
                                t['pyramided'] = True
                            if t['ticket'] == db_pyramid['ticket']:
                                t['is_pyramid'] = True
                        executor.save_state(current_state)

            
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
            is_news_active = latest_indicators.get('news_event_active', False)
            
            if Config.SMART_FILTER and not is_news_active and run_ai:
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

            # --- IMPROVEMENT 1: TIME GUARD (Gate 0) ---
            # Block Asian Session (00:00 to 08:00 UTC) and Weekends
            # Note: News can override the weekend/asian session if explicitly detected, but usually news is during NY/LDN.
            if run_ai and not is_news_active:
                current_utc = datetime.now(timezone.utc)
                is_weekend = current_utc.weekday() >= 5 # 5=Sat, 6=Sun
                is_asian_session = 0 <= current_utc.hour < 8
                
                if is_weekend:
                    decision['reasoning_summary'] = "Time Guard: Weekend Trading Blocked."
                    run_ai = False
                    print("DEBUG: Gate 0 (Time Guard) Blocked. It is the weekend.", flush=True)
                elif is_asian_session:
                    decision['reasoning_summary'] = "Time Guard: Asian Session (00:00-08:00 UTC) Blocked."
                    run_ai = False
                    print(f"DEBUG: Gate 0 (Time Guard) Blocked. Asian Session active ({current_utc.hour:02d}:00 UTC).", flush=True)

            # Gate 1: Spread Guard (Critical during News) - GOLD OPTIMIZED
            spread = latest_indicators.get('spread', 0)
            # Use Gold-specific spread tolerance (50 pts vs 20 pts for forex)
            # During News Arbitrage we anticipate spread widening, so we increase the tolerance
            effective_max_spread = Config.MAX_SPREAD_POINTS * 3 if is_news_active else Config.MAX_SPREAD_POINTS
            
            if run_ai and not risk_manager.validate_spread(spread, effective_max_spread):
                 decision['reasoning_summary'] = f"Spread High ({spread} > {effective_max_spread}). Paused."
                 run_ai = False
                 print(f"DEBUG: Gate 1 (Spread) Blocked. Spread: {spread} > {effective_max_spread}", flush=True)

            # Gate 2: MTF Alignment Check (The Matrix)
            # IGNORE IF NEWS SIGNAL
            print(f"DEBUG: Checking Gate 2. alignment_score={alignment_score}, run_ai={run_ai}", flush=True)
            # SCALPING TWEAK: Relaxed alignment check. 
            # 0.0 was too strict (blocked ranging markets). -0.5 allows "Weak Conflict" / Ranging.
            if run_ai and not is_news_active and alignment_score < -0.5:
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
                    
                    # --- IMPROVEMENT 2A: ENERGY STATE GUARD (Volatility Squeeze) ---
                    # Only apply to momentum-hungry bots
                    source_reason = str(darwin_signal.get('reason', ''))
                    if "MACD" in source_reason or "TrendHawk" in source_reason:
                         is_squeezing = latest_indicators.get('squeeze_on', False)
                         if not is_squeezing:
                             print(f"DEBUG: ⛔ Energy State Guard blocked {darwin_signal['action']}. Volatility is ALREADY EXPANDED (No Squeeze).", flush=True)
                             decision['reasoning_summary'] = "VETO: Volatility Expanded. Missed origin of impulse."
                             run_ai = False


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
                # SAFEGUARD: Prevent Division by Zero
                safe_price = current_price if current_price > 0 else 1.0
                current_vol = atr_val / safe_price
                
                features = {'price': current_price, 'atr': atr_val, 'volatility': current_vol}
                
                # Hybrid: Use Bootstrap if possible, else Monte Carlo
                futures = weaver.generate_historical_echoes(features, n_futures=50, horizon=48) # 4 Hours (was 12/1h)
                
                # 3. Simulate The Jury's Call
                # FIX: Use Darwin's SL/TP if available, else fallback to ATR
                sim_action = darwin_signal.get('action', 'HOLD')
                
                if sim_action in ['BUY', 'SELL']:
                    # Use Darwin's precise SL/TP distances
                    darwin_sl = darwin_signal.get('sl', 0)
                    darwin_tp = darwin_signal.get('tp', 0)
                    
                    if darwin_sl != 0 and darwin_tp != 0:
                        sim_sl_dist = abs(current_price - darwin_sl)
                        sim_tp_dist = abs(darwin_tp - current_price)
                        print(f"🔮 Chronos using Darwin SL/TP: SL_dist={sim_sl_dist:.5f}, TP_dist={sim_tp_dist:.5f}")
                    else:
                        # Fallback to ATR-based distances
                        sim_sl_dist = atr_val * 1.5
                        sim_tp_dist = atr_val * 2.5
                        print(f"🔮 Chronos fallback to ATR: SL_dist={sim_sl_dist:.5f}, TP_dist={sim_tp_dist:.5f}")
                    
                    sim_result = chronos_arena.run_simulation(
                        signal_type=sim_action, 
                        futures=futures, 
                        entry_price=current_price, 
                        sl_dist=sim_sl_dist,
                        tp_dist=sim_tp_dist
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

            # D. DECISION ASSEMBLY (Darwin Signal = Binding Vote)
            # FIX: Darwin's consensus is now THE decision. Groq AI removed from decision chain.
            # GOLD Confirmations still apply to boost/reduce confidence.
            analyzed_decision = {}  # BUG FIX #3: Initialize to prevent undefined variable crash
            
            if run_ai:
                # Darwin's signal IS the decision
                analyzed_decision = {
                    'action': darwin_signal.get('action', 'HOLD'),
                    'confidence_score': darwin_signal.get('confidence', 0.5),
                    'reasoning_summary': darwin_signal.get('reason', 'Darwin Jury'),
                    'source': darwin_signal.get('source', 'Darwin'),
                }
                
                # Preserve Chronos result if it passed
                if 'chronos_result' in decision:
                    analyzed_decision['chronos_result'] = decision['chronos_result']

                # GOLD ENTRY CONFIRMATIONS (Boost/Reduce Confidence)
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

                # Gate D: GROQ AI CONFIDENCE MODIFIER
                # Darwin's action is BINDING. Groq can only adjust confidence, never change direction.
                if analyzed_decision['action'] in ['BUY', 'SELL']:
                    try:
                        print("🤖 Groq AI analyzing market context...", flush=True)
                        groq_decision = ai_strategist.get_trade_decision(market_summary, "")
                        groq_action = groq_decision.get('action', 'HOLD')
                        groq_reasoning = groq_decision.get('reasoning_summary', '')
                        
                        pre_groq_conf = analyzed_decision['confidence_score']
                        
                        if groq_action == analyzed_decision['action']:
                            # AI AGREES → Boost confidence
                            analyzed_decision['confidence_score'] = min(pre_groq_conf + 0.15, 0.95)
                            print(f"🤖 Groq AGREES ({groq_action}): Confidence {pre_groq_conf:.2f} → {analyzed_decision['confidence_score']:.2f} (+0.15)")
                        elif groq_action == 'HOLD':
                            # AI is uncertain → Small penalty
                            analyzed_decision['confidence_score'] = max(pre_groq_conf - 0.10, 0.0)
                            print(f"🤖 Groq UNCERTAIN (HOLD): Confidence {pre_groq_conf:.2f} → {analyzed_decision['confidence_score']:.2f} (-0.10)")
                        else:
                            # AI DISAGREES (opposite direction) → Larger penalty
                            analyzed_decision['confidence_score'] = max(pre_groq_conf - 0.20, 0.0)
                            print(f"🤖 Groq DISAGREES ({groq_action} vs {analyzed_decision['action']}): Confidence {pre_groq_conf:.2f} → {analyzed_decision['confidence_score']:.2f} (-0.20)")
                        
                        # Append AI reasoning to decision
                        analyzed_decision['reasoning_summary'] = f"{analyzed_decision.get('reasoning_summary', '')} | AI: {groq_reasoning}"
                    except Exception as e:
                        print(f"🤖 Groq AI skipped (error: {e}). Using Darwin confidence as-is.")

                decision = risk_manager.validate_signal(analyzed_decision)
                
            # Log State
            swarm_state = darwin.get_swarm_state()
            
            # ORACLE BRIEFING
            # NOTE (Flaw 7): darwin.leader is INFORMATIONAL ONLY — used for dashboard/Oracle, NOT trade decisions.
            # Trade decisions come from get_consensus_signal() (Jury vote), not the leader.
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
            execution_info = None  # FIX: Reset for loop iteration
            if decision['action'] in ["BUY", "SELL"]:
                # Position Sizing
                atr = df.iloc[-1]['ATR_14']
                
                # FIX (Flaw 4 + 11): Use Darwin's SL/TP if available, else fallback to ATR
                # Also renamed mtf_analysis to exec_mtf_analysis to avoid variable shadowing (Flaw 11)
                darwin_sl_exec = decision.get('sl', darwin_signal.get('sl', 0) if 'darwin_signal' in dir() else 0)
                darwin_tp_exec = decision.get('tp', darwin_signal.get('tp', 0) if 'darwin_signal' in dir() else 0)
                
                if darwin_sl_exec != 0 and darwin_tp_exec != 0:
                    # Use Darwin's precise SL/TP
                    sl_price = darwin_sl_exec
                    tp_price = darwin_tp_exec
                    print(f"📐 Using Darwin SL/TP: SL={sl_price:.5f}, TP={tp_price:.5f}")
                else:
                    # FALLBACK: ATR-based SL/TP
                    sl_mult = decision.get("stop_loss_atr_multiplier", 2.5)  # GOLD: Default 2.5
                    
                    # ADAPTIVE STOP LOSS based on Market Regime
                    exec_mtf_analysis = mtf_data.get('analysis', {})
                    exec_mtf_stats = exec_mtf_analysis.get('mtf_stats', {})
                    base_stats = exec_mtf_stats.get('BASE', {})
                    hurst = base_stats.get('hurst', 0.5)
                    entropy = base_stats.get('entropy', 0.7)
                    
                    if hurst > 0.6:
                        sl_mult *= 1.5
                        print(f"📊 Adaptive SL (GOLD): Trending market (H={hurst:.2f}), widening stops by 50%")
                    elif hurst < 0.4:
                        sl_mult *= 0.9
                        print(f"📊 Adaptive SL (GOLD): Ranging market (H={hurst:.2f}), tightening stops by 10%")
                    
                    if entropy < 0.5:
                        sl_mult *= 0.95
                        print(f"📊 Adaptive SL (GOLD): Low entropy ({entropy:.2f}), tightening by 5%")
                    
                    if decision['action'] == "BUY":
                        sl_price = current_price - (atr * sl_mult)
                        tp_price = current_price + ((current_price - sl_price) * 2.0)
                    else:
                        sl_price = current_price + (atr * sl_mult)
                        tp_price = current_price - ((sl_price - current_price) * 2.0)
                    print(f"📐 Using ATR Fallback SL/TP: SL={sl_price:.5f}, TP={tp_price:.5f}")

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
                
                # --- IMPROVEMENT 2B: SWARM-KELLY DYNAMIC BET SIZING ---
                # Dynamically scale risk utilizing the intersection of Swarm Confidence and Chronos WinProb
                swarm_conf = decision.get('confidence_score', 0.5)
                chronos_winrate = decision.get('chronos_result', {}).get('win_rate', 0.5) if 'chronos_result' in decision else 0.5
                
                risk_multiplier = 1.0
                
                if swarm_conf >= 0.85 and chronos_winrate >= 0.75:
                    risk_multiplier = 1.5  # Bet Aggressive (High Conviction)
                    print(f"🔥 SWARM-KELLY MATRIX: High Conviction (Conf: {swarm_conf:.2f}, Chronos: {chronos_winrate:.2f}). Scaling risk 1.5x!")
                elif swarm_conf <= 0.60 or chronos_winrate <= 0.55:
                    risk_multiplier = 0.5  # Bet Defensive (Low Conviction)
                    print(f"🛡️ SWARM-KELLY MATRIX: Low Conviction (Conf: {swarm_conf:.2f}, Chronos: {chronos_winrate:.2f}). Slashing risk 0.5x!")
                else:
                    print(f"⚖️ SWARM-KELLY MATRIX: Neutral Conviction (Conf: {swarm_conf:.2f}, Chronos: {chronos_winrate:.2f}). Base risk 1.0x")
                
                units *= risk_multiplier
                units = max(round(units, 2), 0.01) # Ensure min volume limits

                # PHASE 77: MARKOV CONVICTION BETTING
                # If the Brain is confused (Low Probability), we scale down.
                # If the Brain is Certain (High Probability), we go full size.
                if 'bif_stats' in locals() and 'regime_confidence' in bif_stats:
                    markov_conf = bif_stats.get('regime_confidence', 0.0)
                    if markov_conf > 0:
                        # Logic: 50% Confidence = 0.75x Size. 90% = 0.95x Size.
                        # Formula: 0.5 + (0.5 * Confidence)
                        markov_mult = 0.5 + (0.5 * markov_conf)
                        # Cap at 1.0 (Strict 1% Risk Compliance)
                        markov_mult = min(1.0, markov_mult)
                        
                        units *= markov_mult
                        print(f"🧠 Markov Conviction: {markov_conf:.1%} Certainty -> {markov_mult:.2f}x Sizing")

                # BUG FIX #9: Removed scout safety halving (scout mode removed)

                execution_info = None
                if units > 0:
                        execution_info = executor.execute_trade(decision['action'], sl_price, tp_price, units)
                
                # Log decision with execution info (if any)
                # Ensure we log even if no trade was taken (HOLD/WAIT), but if taken, include details
                dashboard.log_decision(decision, execution_info)
            
            # REALITY CHECK: Report BLOCKED signals
            # If Darwin had a signal (BUY/SELL) but we didn't execute (units=0 or blocked upstream)
            if 'darwin_signal' in locals():
                darwin_action = darwin_signal.get('action', 'HOLD')
                
                if darwin_action in ['BUY', 'SELL']:
                    # We wanted to trade. Did we?
                    executed = False
                    if 'execution_info' in locals() and execution_info:
                        executed = True
                        
                    if not executed:
                         # BLOCKED!
                         source = darwin_signal.get('source', '')
                         if source and source != "Unknown":
                             # We simulate a "Blocked" event
                             darwin.report_execution({'source': source}, 'BLOCKED')
                             print(f"🛑 Darwin Feedback: Signal from {source} BLOCKED by System.")

            # F. Daily Evolution Check (Maintenance)
            
            # PHASE 9: DAWN OF A NEW DAY (EVOLUTION TRIGGER)
            # Check for midnight (local time or server time) to run evolution
            # Let's say between 00:00 and 01:00 we evolve once.
            now_hour = datetime.now().hour
            if now_hour == 0:
                if 'evolved_today' not in locals() or not locals()['evolved_today']:
                    print("🌌 MIDNIGHT EVENT: Initiating Darwinian Evolution Phase...")
                    darwin.evolve_population()
                    locals()['evolved_today'] = True
            elif now_hour > 1:
                 # Reset flag after 1 AM
                 locals()['evolved_today'] = False

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
