import os
os.environ['DO_NOT_TELEMETRY'] = '1'

import pandas as pd
from app.darwin_engine import DarwinEngine

with open('debug_jury.txt', 'w', encoding='utf-8') as f:
    f.write("Initializing Darwin Engine...\n")
    darwin = DarwinEngine()
    
    f.write(f"Total strategies: {len(darwin.strategies)}\n")
    
    allowed = [
        "MeanReverter_LONG", "MeanReverter_SHORT", 
        "RSI_Matrix_LONG", "RSI_Matrix_SHORT", 
        "TrendHawk_LONG", "TrendHawk_SHORT", 
        "TrendPullback_LONG", "TrendPullback_SHORT", 
        "MACD_Cross_LONG", "MACD_Cross_SHORT", 
        "Sniper_Elite", "LiquiditySweeper_LONG"
    ]

    tag_map = {
        "MeanReverter_LONG": ["MeanRev_LONG"],
        "MeanReverter_SHORT": ["MeanRev_SHORT"],
        "RSI_Matrix_LONG": ["RSI_", "_LONG"],
        "RSI_Matrix_SHORT": ["RSI_", "_SHORT"],
        "TrendHawk_LONG": ["TrendHawk_LONG"],
        "TrendHawk_SHORT": ["TrendHawk_SHORT"],
        "TrendPullback_LONG": ["TrendPullback_LONG"],
        "TrendPullback_SHORT": ["TrendPullback_SHORT"],
        "MACD_Cross_LONG": ["MACD_Cross_LONG"],
        "MACD_Cross_SHORT": ["MACD_Cross_SHORT"],
        "Sniper_Elite": ["Sniper_Elite"],
        "LiquiditySweeper_LONG": ["LiquiditySweeper", "LONG"],
        "LiquiditySweeper_SHORT": ["LiquiditySweeper", "SHORT"],
        "NewsArbitrage_LONG": ["NewsArbitrage", "LONG"],
        "NewsArbitrage_SHORT": ["NewsArbitrage", "SHORT"],
        "StatArb_DXY_LONG": ["StatArb_DXY", "LONG"],
        "StatArb_DXY_SHORT": ["StatArb_DXY", "SHORT"]
    }

    candidates = []
    for strat in darwin.strategies:
         is_match = False
         for allow_tag in allowed:
             search_terms = tag_map.get(allow_tag, [allow_tag])
             if all(term in strat.name for term in search_terms):
                 is_match = True
                 break
                 
             if allow_tag.endswith("_LONG") or allow_tag.endswith("_SHORT"):
                 both_terms = [t.replace("LONG", "BOTH").replace("SHORT", "BOTH") for t in search_terms]
                 if all(term in strat.name for term in both_terms):
                     is_match = True
                     break
                     
         if is_match:
             candidates.append(strat)
             
    f.write(f"Filtered Candidate count: {len(candidates)}\n")
    f.write(f"Candidates: {[c.name for c in candidates]}\n")

    jury = []
    strategy_types = ["TrendHawk", "MeanRev", "RSI_Matrix", "MACD_Cross", "Sniper", "TrendPullback", "LiquiditySweeper", "NewsArbitrage", "StatArb"]
    top_n = 5

    for strategy_type in strategy_types:
        for strat in candidates:
            if strategy_type in strat.name and strat not in jury:
                jury.append(strat)
                break
        if len(jury) >= top_n:
            break

    if len(jury) < top_n:
        for strat in candidates:
            if strat not in jury:
                jury.append(strat)
            if len(jury) >= top_n:
                break

    f.write(f"Jury list: {[s.name for s in jury]}\n")
