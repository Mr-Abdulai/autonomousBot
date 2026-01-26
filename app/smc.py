import pandas as pd
from app.ta_lib import TALib

class SMCEngine:
    """
    SMC Logic Engine.
    Encapsulates logic for detecting Order Blocks, FVGs, and Swings.
    """
    def __init__(self):
        pass

    def detect_swings(self, df: pd.DataFrame, length: int = 5):
        """
        Identifies Fractal Swing Highs and Lows.
        Returns the dataframe with 'is_swing_high' and 'is_swing_low' columns.
        """
        df['is_swing_high'] = False
        df['is_swing_low'] = False
        
        for i in range(length, len(df) - length):
            # Swing High
            if df['high'].iloc[i] == df['high'].iloc[i-length:i+length+1].max():
                df.at[df.index[i], 'is_swing_high'] = True
                
            # Swing Low
            if df['low'].iloc[i] == df['low'].iloc[i-length:i+length+1].min():
                df.at[df.index[i], 'is_swing_low'] = True
                
        return df

    def detect_fvgs(self, df: pd.DataFrame) -> list:
        """
        Scans for Fair Value Gaps (FVGs) aka Imbalances.
        Returns a list of FVG dicts.
        """
        fvgs = []
        # Scan last 50 candles
        for i in range(len(df) - 50, len(df) - 2): # Need i, i+1, i+2
            # Bullish FVG: (High of i) < (Low of i+2)
            # Candle i+1 is the displacement candle
            candle_1_high = df.iloc[i]['high']
            candle_3_low = df.iloc[i+2]['low']
            
            if candle_3_low > candle_1_high:
                fvgs.append({
                    "type": "BULLISH_FVG",
                    "top": candle_3_low,
                    "bottom": candle_1_high,
                    "time": str(df.iloc[i+1]['time']),
                    "index": i+1 # The FVG is formed by the middle candle
                })
                
            # Bearish FVG: (Low of i) > (High of i+2)
            candle_1_low = df.iloc[i]['low']
            candle_3_high = df.iloc[i+2]['high']
            
            if candle_1_low > candle_3_high:
                fvgs.append({
                    "type": "BEARISH_FVG",
                    "top": candle_1_low,
                    "bottom": candle_3_high,
                    "time": str(df.iloc[i+1]['time']),
                    "index": i+1
                })
                
        return fvgs

    def check_displacement_with_fvg(self, df: pd.DataFrame, index: int, direction: str, fvgs: list) -> bool:
        """
        Checks if there is significant displacement AND an FVG created 
        shortly after the swing point (within next 3 candles).
        """
        try:
            # 1. ATR Check (Strong Move)
            # Ensure ATR exists or calc on fly if critically needed, but usually pre-calculated.
            if 'ATR_14' in df.columns:
                 atr = df['ATR_14'].iloc[index]
            else:
                 atr = 0.0 # Fallback
            
            # Look for FVG in the next 1-4 candles
            found_fvg = False
            limit_idx = min(index + 5, len(df))
            
            for fvg in fvgs:
                # Check if FVG index is close to our swing point
                if index < fvg['index'] <= limit_idx:
                    if direction == "UP" and fvg['type'] == "BULLISH_FVG":
                        found_fvg = True
                    elif direction == "DOWN" and fvg['type'] == "BEARISH_FVG":
                        found_fvg = True
            
            if not found_fvg:
                return False
                
            return True
                
        except Exception as e:
            return False
        return False

    def calculate_smc(self, df: pd.DataFrame) -> dict:
        """
        Main SMC Engine.
        Returns dictionary with Active Order Blocks and FVGs.
        """
        if df is None or len(df) < 50:
            return {"order_blocks": [], "fvgs": [], "structure": "Unknown"}

        # ensure ATR exists
        if 'ATR_14' not in df.columns:
            df['ATR_14'] = TALib.atr(df, 14)

        df = self.detect_swings(df)
        
        # 1. Detect all FVGs first
        all_fvgs = self.detect_fvgs(df)
        
        order_blocks = []
        
        # Scan for Order Blocks (Last 100 candles only for performance)
        lookback = 100
        start_idx = max(0, len(df) - lookback)
        
        for i in range(start_idx, len(df) - 5): # -5 buffer for validation
            
            # Bullish OB Candidate (Swing Low)
            if df.iloc[i]['is_swing_low']:
                # Validation: Must create Bullish FVG shortly after
                if self.check_displacement_with_fvg(df, i, "UP", all_fvgs):
                    ob = {
                        "type": "BULLISH_OB",
                        "price_top": df.iloc[i]['high'], # Refinement: Top of Swing Candle
                        "price_bottom": df.iloc[i]['low'],
                        "time": str(df.iloc[i]['time']),
                        "index": i,
                        "mitigated": False
                    }
                    # Check Mitigation
                    future_lows = df['low'].iloc[i+5:]
                    if not future_lows.empty and future_lows.min() <= ob['price_top']:
                        ob['mitigated'] = True
                    
                    order_blocks.append(ob)

            # Bearish OB Candidate (Swing High)
            if df.iloc[i]['is_swing_high']:
                # Validation: Must create Bearish FVG shortly after
                if self.check_displacement_with_fvg(df, i, "DOWN", all_fvgs):
                    ob = {
                        "type": "BEARISH_OB",
                        "price_top": df.iloc[i]['high'],
                        "price_bottom": df.iloc[i]['low'],
                        "time": str(df.iloc[i]['time']),
                        "index": i,
                        "mitigated": False
                    }
                    # Check Mitigation
                    future_highs = df['high'].iloc[i+5:]
                    if not future_highs.empty and future_highs.max() >= ob['price_bottom']:
                        ob['mitigated'] = True
                        
                    order_blocks.append(ob)
        
        # Filter for only Fresh (Unmitigated) OBs
        fresh_obs = [ob for ob in order_blocks if not ob['mitigated']]
        
        # Sort by recent
        fresh_obs.sort(key=lambda x: x['index'], reverse=True)
        
        return {
            "order_blocks": fresh_obs[:3], # Return top 3 freshest
            "fvgs": all_fvgs[-5:], # Return last 5 FVGs context
            "structure": "Trend Following"
        }
