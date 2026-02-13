"""
SHORT TRADE DIAGNOSTIC SCRIPT
==============================
This script diagnoses WHY the bot favours LONG over SHORT trades.
It checks: BIF regime analysis, Jury composition, strategy directional filtering.

Run: python diagnose_short_bias.py
Requires: The same environment as main.py (MT5, .env, etc.)
"""
import json
import os
import sys
import pandas as pd
import MetaTrader5 as mt5
from dotenv import load_dotenv

load_dotenv()

# --- Setup ---
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app.config import Config
from app.market_sensor import MarketSensor
from app.bif_brain import BIFBrain
from app.darwin_engine import DarwinEngine

def main():
    print("=" * 70)
    print("SHORT TRADE DIAGNOSTIC REPORT")
    print("=" * 70)
    
    # 1. Initialize MT5
    if not mt5.initialize():
        print("❌ MT5 initialization failed. Cannot run diagnostic.")
        return
    
    symbol = Config.SYMBOL
    print(f"\n📌 Symbol: {symbol}")
    
    # 2. Get Market Data
    sensor = MarketSensor()
    df, indicators = sensor.get_latest_data(symbol)
    mtf_data_raw = sensor.get_multi_timeframe_data(symbol)
    
    if df is None or df.empty:
        print("❌ No market data available.")
        mt5.shutdown()
        return
    
    current_price = df.iloc[-1]['close']
    print(f"📌 Current Price: {current_price:.5f}")
    
    # 3. BIF BRAIN ANALYSIS (THE KEY)
    print("\n" + "=" * 70)
    print("SECTION 1: BIF BRAIN REGIME ANALYSIS")
    print("=" * 70)
    
    bif = BIFBrain()
    
    # Analyze each timeframe individually
    for tf_name, tf_df in mtf_data_raw.items():
        if tf_df is not None and not tf_df.empty:
            close = tf_df['close'].iloc[-1]
            ema50 = tf_df['close'].ewm(span=50).mean().iloc[-1]
            trend = "BULLISH" if close > ema50 else "BEARISH"
            
            stats = bif.analyze_market_state(tf_df)
            hurst = stats.get('hurst', 0.5)
            entropy_val = stats.get('entropy', 0.5)
            
            print(f"\n  {tf_name}:")
            print(f"    Close: {close:.5f} | EMA50: {ema50:.5f}")
            print(f"    Trend: {trend} | Hurst: {hurst:.3f} | Entropy: {entropy_val:.3f}")
    
    # Full MTF analysis
    mtf_analysis = bif.analyze_mtf_regime(mtf_data_raw)
    
    print(f"\n  🧠 BIF VERDICT:")
    print(f"    Trend Status: {mtf_analysis.get('trend', 'UNKNOWN')}")
    print(f"    Alignment Score: {mtf_analysis.get('alignment_score', 0)}")
    print(f"    Scout Mode: {mtf_analysis.get('scout_mode', False)}")
    print(f"    Allowed Strategies: {mtf_analysis.get('allowed_strategies', [])}")
    
    allowed = mtf_analysis.get('allowed_strategies', ['ALL'])
    
    # CHECK: Are SHORT strategies allowed?
    has_short = any('SHORT' in s for s in allowed) or 'ALL' in allowed
    has_long = any('LONG' in s for s in allowed) or 'ALL' in allowed
    
    if not has_short:
        print(f"\n  ⚠️  BIF IS BLOCKING ALL SHORT STRATEGIES!")
        print(f"    This is why the bot only takes LONG trades.")
        print(f"    BIF sees: {mtf_analysis.get('summary', '')}")
    elif not has_long:
        print(f"\n  ✅ BIF allows SHORT only (bearish pullback)")
    else:
        print(f"\n  ✅ BIF allows both LONG and SHORT")
    
    # 4. DARWIN SWARM ANALYSIS
    print("\n" + "=" * 70)
    print("SECTION 2: DARWIN SWARM COMPOSITION")
    print("=" * 70)
    
    darwin = DarwinEngine()
    darwin.load_state()
    
    # Update phantom equity with current price
    for strat in darwin.strategies:
        strat.update_performance(current_price)
    
    # Sort and show top strategies
    darwin.strategies.sort(key=lambda s: s.get_quality_score(), reverse=True)
    darwin.leader = darwin.strategies[0] if darwin.strategies else None
    
    long_count = sum(1 for s in darwin.strategies if s.direction == 'LONG')
    short_count = sum(1 for s in darwin.strategies if s.direction == 'SHORT')
    both_count = sum(1 for s in darwin.strategies if s.direction == 'BOTH')
    
    print(f"\n  Total Strategies: {len(darwin.strategies)}")
    print(f"  LONG: {long_count} | SHORT: {short_count} | BOTH: {both_count}")
    print(f"  Leader: {darwin.leader.name if darwin.leader else 'None'}")
    
    # Top 10 by score
    print(f"\n  Top 10 by Quality Score:")
    for i, s in enumerate(darwin.strategies[:10]):
        score = s.get_quality_score()
        print(f"    {i+1}. {s.name:30s} | Dir: {s.direction:5s} | Equity: {s.phantom_equity:>14.2f} | Score: {score:.2f}")
    
    # Bottom 5
    print(f"\n  Bottom 5:")
    for s in darwin.strategies[-5:]:
        score = s.get_quality_score()
        print(f"    - {s.name:30s} | Dir: {s.direction:5s} | Equity: {s.phantom_equity:>14.2f} | Score: {score:.2f}")
    
    # 5. JURY SIMULATION
    print("\n" + "=" * 70)
    print("SECTION 3: JURY COMPOSITION (Who gets selected?)")
    print("=" * 70)
    
    mtf_data = mtf_data_raw.copy()
    mtf_data['analysis'] = mtf_analysis
    
    # Simulate jury selection
    signal = darwin.get_consensus_signal(df, indicators, mtf_data)
    
    print(f"\n  Jury Action: {signal.get('action', 'UNKNOWN')}")
    print(f"  Confidence: {signal.get('confidence', 0):.2f}")
    print(f"  Reason: {signal.get('reason', 'N/A')[:200]}")
    print(f"  Votes: {signal.get('jury_votes', {})}")
    
    # 6. INDIVIDUAL STRATEGY TEST
    print("\n" + "=" * 70)
    print("SECTION 4: RAW SIGNAL FROM EVERY STRATEGY")
    print("=" * 70)
    
    for strat in darwin.strategies:
        raw = strat._generate_raw_signal(df, indicators, mtf_data)
        filtered = strat.generate_signal(df, indicators, mtf_data)
        
        if raw['action'] != 'HOLD' or filtered['action'] != 'HOLD':
            raw_action = raw['action']
            filtered_action = filtered['action']
            was_filtered = raw_action != filtered_action
            
            marker = "🔴 FILTERED" if was_filtered else "✅"
            print(f"  {marker} {strat.name:30s} | Raw: {raw_action:5s} → Final: {filtered_action:5s} | Reason: {raw.get('reason', '')[:60]}")
    
    # Count
    raw_sells = sum(1 for s in darwin.strategies if s._generate_raw_signal(df, indicators, mtf_data)['action'] == 'SELL')
    raw_buys = sum(1 for s in darwin.strategies if s._generate_raw_signal(df, indicators, mtf_data)['action'] == 'BUY')
    
    filtered_sells = sum(1 for s in darwin.strategies if s.generate_signal(df, indicators, mtf_data)['action'] == 'SELL')
    filtered_buys = sum(1 for s in darwin.strategies if s.generate_signal(df, indicators, mtf_data)['action'] == 'BUY')
    
    print(f"\n  Summary:")
    print(f"    Raw Signals:      BUY={raw_buys}, SELL={raw_sells}")
    print(f"    After Filtering:  BUY={filtered_buys}, SELL={filtered_sells}")
    print(f"    Filtered Out:     BUY={raw_buys - filtered_buys}, SELL={raw_sells - filtered_sells}")
    
    if raw_sells > 0 and filtered_sells == 0:
        print(f"\n  ⚠️  {raw_sells} SELL signals existed but ALL were filtered out by directional constraints!")
        print(f"    LONG strategies detected SELL conditions but can't act on them.")
    
    # 7. DIAGNOSIS SUMMARY
    print("\n" + "=" * 70)
    print("DIAGNOSIS SUMMARY")
    print("=" * 70)
    
    issues = []
    
    if not has_short:
        issues.append(f"BIF restricts to LONG-only (Regime: {mtf_analysis.get('trend', '?')})")
    
    if raw_sells > filtered_sells:
        issues.append(f"{raw_sells - filtered_sells} SELL signals filtered by directional constraints")
    
    if raw_sells == 0:
        issues.append("No strategy produces a SELL signal at current price levels")
    
    long_top = sum(1 for s in darwin.strategies[:10] if s.direction == 'LONG')
    if long_top > 7:
        issues.append(f"Top 10 strategies are {long_top}/10 LONG (LONG domination)")
    
    if issues:
        print("\n  🔴 ISSUES FOUND:")
        for i, issue in enumerate(issues, 1):
            print(f"    {i}. {issue}")
    else:
        print("\n  ✅ No obvious SHORT bias detected at current market state.")
    
    mt5.shutdown()
    print("\n" + "=" * 70)
    print("END OF DIAGNOSTIC")
    print("=" * 70)

if __name__ == "__main__":
    main()
