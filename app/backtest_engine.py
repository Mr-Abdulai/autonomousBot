import pandas as pd
import numpy as np
import MetaTrader5 as mt5
from datetime import datetime
import time
from app.config import Config
from app.market_sensor import MarketSensor
from app.darwin_engine import DarwinEngine
from app.ta_lib import TALib
from app.smc import SMCEngine # Phase 8

class VirtualBroker:
    """
    Simulates Trade Execution and PnL tracking without MT5 orders.
    """
    def __init__(self, initial_capital=10000.0, spread_points=20, leverage=500):
        self.balance = initial_capital
        self.equity = initial_capital
        self.initial_capital = initial_capital
        self.leverage = leverage
        self.open_trades = []
        self.trade_history = []
        self.spread_points = spread_points # 20 points = 2 pips
        
    def execute(self, signal, current_price, time):
        # 1. Check Limits
        if len(self.open_trades) >= Config.MAX_OPEN_TRADES:
            return
            
        action = signal['action']
        if action not in ['BUY', 'SELL']:
            return
            
        # 2. Simulate Spread Cost
        # BUY executes at ASK (Price + Spread)
        # SELL executes at BID (Price)
        # For simplicity, we assume 'current_price' is BID.
        point = 0.01 # Standardize?
        entry_price = current_price
        
        if action == 'BUY':
            entry_price = current_price + (self.spread_points * point)
            
        # 3. Dynamic Lot Size (Risk Management)
        # Risk 2% of Equity
        risk_per_trade = self.equity * 0.02
        sl = signal.get('sl', 0)
        tp = signal.get('tp', 0)
        
        # Validation
        if sl == 0 or tp == 0: return
        
        # Distance to SL (Price points)
        dist_price = abs(entry_price - sl)
        if dist_price == 0: return
        
        # Value per Lot logic:
        # XAUUSD Contract Size = 100
        # Loss = dist_price * 100 * Lots
        # Lots = Risk / (dist_price * 100)
        contract_size = 100 # XAUUSD Standard
        if 'JPY' in str(signal.get('symbol', '')): contract_size = 1000
        
        volume = risk_per_trade / (dist_price * contract_size)
        volume = round(volume, 2)
        
        # Micro-Account Logic: If calculated volume is 0.00 but signals are valid,
        # Force 0.01 (Min Lot). This means risk % will be exceeded!
        if volume < 0.01:
            volume = 0.01
            # Optional: Log warning?
            # print(f"⚠️ forced min lot 0.01 (Risk Exceeded)")
        
        # 4. Leverage / Margin Check
        # Margin = (Price * Contract * Volume) / Leverage
        margin_required = (entry_price * contract_size * volume) / self.leverage
        free_margin = self.equity - sum([(t['open_price']*contract_size*t['volume'])/self.leverage for t in self.open_trades])
        
        if margin_required > free_margin:
            # print(f"⚠️ Trade Skipped: Insufficient Margin. Req: {margin_required:.2f}, Free: {free_margin:.2f}")
            return

        trade = {
            'ticket': len(self.trade_history) + len(self.open_trades) + 1,
            'symbol': 'BACKTEST',
            'type': action,
            'open_price': entry_price,
            'sl': sl,
            'tp': tp,
            'volume': volume,
            'open_time': time,
            'profit': 0.0
        }
        self.open_trades.append(trade)
        # print(f"[{time}] OPEN {action} {volume} lots @ {entry_price:.2f}")

    def update(self, current_candle):
        """
        Updates floating PnL and checks SL/TP hits.
        Candle has: time, open, high, low, close.
        """
        high = current_candle['high']
        low = current_candle['low']
        # approximate price path: Open -> Low -> High -> Close (Bullish) or Open -> High -> Low -> Close
        # Conservative: Check SL first unless gap?
        
        completed_trades = []
        
        current_bid = current_candle['close']
        current_ask = current_bid + (self.spread_points * 0.01) # Spread approximation
        
        for trade in self.open_trades:
            close_price = 0.0
            reason = ""
            pnl = 0.0
            closed = False
            
            # CHECK EXITS
            if trade['type'] == 'BUY':
                # SL HIT (Bid hits SL)
                if low <= trade['sl']:
                    close_price = trade['sl']
                    reason = "SL"
                    closed = True
                # TP HIT (Bid hits TP)
                elif high >= trade['tp']:
                    close_price = trade['tp']
                    reason = "TP"
                    closed = True
                else:
                    # Update Floating
                    trade['profit'] = (current_bid - trade['open_price']) * 100 * trade['volume']
                    
            elif trade['type'] == 'SELL':
                # SL HIT (Ask hits SL) -> High + Spread >= SL
                if (high + (self.spread_points*0.01)) >= trade['sl']:
                    close_price = trade['sl']
                    reason = "SL"
                    closed = True
                # TP HIT (Ask hits TP) -> Low + Spread <= TP
                elif (low + (self.spread_points*0.01)) <= trade['tp']:
                    close_price = trade['tp']
                    reason = "TP"
                    closed = True
                else:
                    # Update Floating
                    trade['profit'] = (trade['open_price'] - current_ask) * 100 * trade['volume']

            if closed:
                # Calculate Final PnL
                contract_size = 100 # XAUUSD
                
                if trade['type'] == 'BUY':
                    # (Exit - Entry) * Contract * Volume
                    pnl = (close_price - trade['open_price']) * contract_size * trade['volume'] 
                else:
                    # (Entry - Exit) * Contract * Volume
                    pnl = (trade['open_price'] - close_price) * contract_size * trade['volume']
                
                trade['close_price'] = close_price
                trade['close_time'] = current_candle['time']
                trade['profit'] = pnl
                trade['reason'] = reason
                
                self.balance += pnl
                self.trade_history.append(trade)
                completed_trades.append(trade)
        
        # Remove closed
        for t in completed_trades:
            self.open_trades.remove(t)
            
        # Update Equity
        floating = sum(t['profit'] for t in self.open_trades)
        self.equity = self.balance + floating

class Backtester:
    def __init__(self, symbol="XAUUSD", timeframe=mt5.TIMEFRAME_M15, initial_capital=10000.0, leverage=500):
        self.symbol = symbol
        self.timeframe = timeframe
        self.sensor = MarketSensor(symbol, timeframe)
        self.darwin = DarwinEngine()
        self.sensor = MarketSensor(symbol, timeframe)
        self.darwin = DarwinEngine()
        self.smc = SMCEngine() # Phase 8
        self.broker = VirtualBroker(initial_capital=initial_capital, leverage=leverage)
        
    def fetch_history(self, days=30):
        print(f"⏳ Fetching {days} days of history for {self.symbol}...")
        if not mt5.initialize():
            print("MT5 Connection Failed")
            return None
            
        # Calculate N candles (approx)
        # M15 = 4 per hour * 24 * days = 96 * days
        count = 96 * days
        # Fetch generous buffer
        df = self.sensor.get_market_data(n_candles=count + 500)
        print(f"✅ Loaded {len(df)} candles.")
        return df
        
    def run(self, days=30):
        df = self.fetch_history(days)
        if df is None or df.empty: return
        
        # PRE-CALCULATE INDICATORS (Vectorized Speed)
        print("🧠 Pre-calculating Indicators...")
        # MarketSensor already calculates them in get_market_data -> calculate_indicators
        # df now has 'RSI_14', 'EMA_50', etc.
        
        # SIMULATION LOOP
        print("🚀 Starting Time Machine...")
        
        start_index = 200 # Need warm up for EMA200
        total_steps = len(df) - start_index
        
        reports = []
        
        import time
        t0 = time.time()
        
        for i in range(start_index, len(df)):
            # Slice "Known World" up to i
            # To simulate live, we just pass the Current Row mostly, 
            # but strategies might need history.
            # Darwin Strategies generally look at df.iloc[-1].
            
            # Optimized: Pass a slice of last 500 to Darwin
            start_window = max(0, i - 500)
            current_slice = df.iloc[start_window : i+1].copy()
            current_candle = current_slice.iloc[-1]
            
            # 1. Update Broker (Check limits/stops on current candle High/Low)
            self.broker.update(current_candle)
            
            # 2. Re-construct Signals Dictionary for Darwin
            # (MarketSensor usually does this live)
            indicators = {
                "close": current_candle['close'],
                "rsi": current_candle['RSI_14'],
                "ema_13": current_candle['EMA_13'],   # Fast EMA for scalping
                "ema_50": current_candle['EMA_50'],
                "ema_200": current_candle['EMA_200'],
                "atr": current_candle['ATR_14'],
                "bb_upper": current_candle['BB_Upper'],
                "bb_lower": current_candle['BB_Lower'],
                "macd": current_candle['MACD'],
                "macd_signal": current_candle['MACDs']
            }
            
            # 3. Darwin Update
            # Creates signals, updates virtual equity of strategies
            # We need to mock 'mtf_data' as well (just using current TF for speed)
            mtf_data = {
                'analysis': {'allowed_strategies': ['ALL']},
                'HTF1': pd.DataFrame(), # Mock empty to avoid expensive fetches
                'BASE': current_slice
            }
            
            self.darwin.update(current_slice, indicators, mtf_data)
            
            # 4. Get Consensus/Alpha Signal
            signal = self.darwin.get_alpha_signal(current_slice, indicators, mtf_data)
            
            # --- GATE 3.5: SMC FILTER (Phase 8 Backtest) ---
            if Config.ENABLE_SMC_FILTER and signal['action'] in ['BUY', 'SELL']:
                smc_data = self.smc.calculate_smc(current_slice)
                valid = False
                action = signal['action']
                close = current_candle['close']
                
                obs = smc_data.get('order_blocks', [])
                fvgs = smc_data.get('fvgs', [])
                
                if action == 'BUY':
                    for ob in obs:
                        if ob['type'] == 'BULLISH_OB' and (ob['price_bottom']*0.999 <= close <= ob['price_top']*1.005):
                            valid = True; break
                    if not valid:
                        for fvg in fvgs:
                             if fvg['type'] == 'BULLISH_FVG' and (fvg['bottom'] <= close <= fvg['top']):
                                 valid = True; break
                                 
                elif action == 'SELL':
                    for ob in obs:
                        if ob['type'] == 'BEARISH_OB' and (ob['price_bottom']*0.995 <= close <= ob['price_top']*1.001):
                            valid = True; break
                    if not valid:
                        for fvg in fvgs:
                             if fvg['type'] == 'BEARISH_FVG' and (fvg['bottom'] <= close <= fvg['top']):
                                 valid = True; break
                
                if not valid:
                    # BLOCK TRADE
                    signal['action'] = 'HOLD'
                    # print("SMC Blocked")

            # 5. Execute
            if signal['action'] != 'HOLD':
                self.broker.execute(signal, current_candle['close'], current_candle['time'])
                
            # Progress Log with Bias Check
            if i % 100 == 0:
                pct = (i - start_index) / total_steps * 100
                leader = signal.get("strategy_name", "None") or "None"
                action = signal.get("action", "HOLD")
                print(f"\rProgress: {pct:.1f}% | Eq: ${self.broker.equity:.0f} | Leader: {leader} ({action})", end="")
                
            # Log for Charting
            reports.append({
                'time': current_candle['time'],
                'equity': self.broker.equity,
                'drawdown': (self.broker.initial_capital - self.broker.equity) / self.broker.initial_capital if self.broker.equity < self.broker.initial_capital else 0
            })
            
        print("\n✅ Simulation Complete.")
        
        # RESULTS
        history = self.broker.trade_history
        wins = len([t for t in history if t['profit'] > 0])
        losses = len([t for t in history if t['profit'] <= 0])
        win_rate = (wins / len(history) * 100) if history else 0
        total_pnl = self.broker.equity - self.broker.initial_capital
        
        print("\n=== BACKTEST RESULTS ===")
        print(f"Symbol: {self.symbol} | Days: {days}")
        print(f"Final Equity: ${self.broker.equity:.2f} ({total_pnl:+.2f})")
        print(f"Total Trades: {len(history)}")
        print(f"Win Rate: {win_rate:.1f}% ({wins}W / {losses}L)")
        
        # Save Report
        pd.DataFrame(reports).to_csv("backtest_equity.csv", index=False)
        pd.DataFrame(history).to_csv("backtest_trades.csv", index=False)
        print("📁 Reports saved: backtest_equity.csv, backtest_trades.csv")
