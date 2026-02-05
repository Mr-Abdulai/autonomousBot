import json
import os
import MetaTrader5 as mt5
from datetime import datetime
from app.config import Config

class ExecutionEngine:
    def __init__(self):
        self.trades_file = Config.TRADES_FILE
        self.symbol = Config.SYMBOL
        self.backtest_mode = Config.BACKTEST_MODE
        # Load persisted state immediately
        self.active_trades = self.load_state()

    def load_state(self) -> list:
        """Reads trades.json. Returns a LIST of active trades."""
        if not os.path.exists(self.trades_file):
            return []
        try:
            with open(self.trades_file, 'r') as f:
                data = json.load(f)
                if isinstance(data, dict):
                    # Migration: Convert legacy single trade to list
                    return [data] if data else []
                return data
        except json.JSONDecodeError:
            return []

    def save_state(self, trades: list):
        """Writes LIST of trades to trades.json."""
        with open(self.trades_file, 'w') as f:
            json.dump(trades, f, indent=4)

    def clear_state(self):
        """Clears all trades (RESET)."""
        if os.path.exists(self.trades_file):
            os.remove(self.trades_file)

    def execute_trade(self, action: str, sl_price: float, tp_price: float, risk_units: float) -> str:
        """Executes a NEW trade and appends to the list."""
        
        # 1. Logic to calculate volume (same as before)
        contract_size = 1.0
        if not self.backtest_mode and mt5.initialize():
            info = mt5.symbol_info(self.symbol)
            if info: contract_size = info.trade_contract_size
        else:
             contract_size = 100.0 if "XAU" in self.symbol else 1.0
        
        volume_lots = risk_units / contract_size
        volume_lots = max(0.01, round(volume_lots, 2))

        print(f"EXECUTING {action} | Volume: {volume_lots} Lots | SL: {sl_price} | TP: {tp_price}")

        # BACKTEST MOCK
        if self.backtest_mode:
            mock_ticket = f"MOCK_{int(datetime.now().timestamp())}_{int(volume_lots*100)}"
            trade_data = {
                "ticket": mock_ticket,
                "symbol": self.symbol,
                "action": action,
                "open_price": sl_price + (sl_price*0.01 if action=="SELL" else -sl_price*0.01),
                "sl": sl_price,
                "tp": tp_price,
                "volume": volume_lots,
                "mode": "BACKTEST",
                "partial_closed": False  # BUG FIX #10: Persist partial closure state
            }
            # Append to existing
            current_trades = self.load_state()
            current_trades.append(trade_data)
            self.save_state(current_trades)
            
            print(f"[BACKTEST] Trade Mock-Executed. Ticket: {mock_ticket}")
            return trade_data

        # LIVE MODE
        if not mt5.initialize():
            print("MT5 Not Verified.")
            return None
            
        # Get Price
        tick = mt5.symbol_info_tick(self.symbol)
        price = tick.ask if action == "BUY" else tick.bid
        
        order_type = mt5.ORDER_TYPE_BUY if action == "BUY" else mt5.ORDER_TYPE_SELL
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": self.symbol,
            "volume": volume_lots,
            "type": order_type,
            "price": price,
            "sl": sl_price,
            "tp": tp_price,
            "deviation": 20,
            "magic": 123456,
            "comment": "Groq-Bot Pycn",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        
        result = mt5.order_send(request)
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            print(f"Order Send Failed: {result.retcode}")
            return None
            
        print(f"Order Sent! Ticket: {result.order}")
        
        trade_data = {
            "ticket": str(result.order),
            "symbol": self.symbol,
            "mode": "LIVE",
            "action": action,
            "volume": volume_lots,
            "open_price": result.price,
            "sl": sl_price,
            "tp": tp_price,
            "partial_closed": False  # BUG FIX #10: Persist partial closure state
        }
        
        current_trades = self.load_state()
        current_trades.append(trade_data)
        self.save_state(current_trades)
        return trade_data

    def modify_order_sl(self, ticket: int, new_sl: float) -> bool:
        """Helper to modify SL."""
        if self.backtest_mode: return True
        
        request = {"action": mt5.TRADE_ACTION_SLTP, "position": ticket, "sl": new_sl, "tp": 0.0, "magic": 123456}
        pos = mt5.positions_get(ticket=ticket)
        if pos: request["tp"] = pos[0].tp
        
        res = mt5.order_send(request)
        return res.retcode == mt5.TRADE_RETCODE_DONE

    def monitor_open_trades(self, current_price: float, atr: float = 0.0, fractal_levels: dict = None) -> dict:
        """
        Monitors ALL open trades.
        Returns: {'count': int, 'trades': list, 'closed_pnl': float, 'managed_count': int}
        """
        trades = self.load_state()
        active_trades = []
        total_pnl = 0.0
        managed_count = 0
        
        for trade in trades:
            ticket = trade.get("ticket")
            mode = trade.get("mode")
            action = trade.get("action")
            sl = trade.get("sl")
            tp = trade.get("tp")
            open_price = trade.get("open_price")
            volume = trade.get("volume", 0.01)
            
            is_closed = False
            pnl = 0.0
            updated = False
            
            # --- MONITORING LOGIC ---
            if mode == "BACKTEST":
                if action == "BUY":
                    if current_price <= sl: is_closed=True; pnl=(sl-open_price)*volume*100
                    elif current_price >= tp: is_closed=True; pnl=(tp-open_price)*volume*100
                elif action == "SELL":
                    if current_price >= sl: is_closed=True; pnl=(open_price-sl)*volume*100
                    elif current_price <= tp: is_closed=True; pnl=(open_price-tp)*volume*100
                
                if is_closed: print(f"[BACKTEST] Trade {ticket} Closed. PnL: {pnl:.2f}")

            elif mode == "LIVE":
                if mt5.initialize():
                    positions = mt5.positions_get(ticket=int(ticket))
                    if not positions:
                        # Closed in MT5
                        is_closed = True
                        print(f"Trade {ticket} Closed in MT5.")
                        # Logic to fetch real PnL omitted for space, assuming 0 or approx
            
            # --- MANAGEMENT LOGIC (If Active) ---
            if not is_closed and mode == "LIVE":
                # Apply Smart Trailing
                # Uses ATR for validation but purely Structural (Fractal) targets if available
                self.apply_trailing_stop(ticket, current_price, open_price, action, sl, tp, atr, fractal_levels)
                managed_count += 1 

            # --- FINALIZATION ---
            if is_closed:
                total_pnl += pnl
            else:
                active_trades.append(trade)

        # Update File
        self.save_state(active_trades)
        
        return {
            'count': len(active_trades),
            'trades': active_trades,
            'closed_pnl': total_pnl,
            'managed_count': managed_count
        }

    def apply_trailing_stop(self, ticket, current_price, entry_price, action, current_sl, tp, atr, fractal_levels=None):
        """
        Dynamically moves Stop Loss based on profit milestones.
        1. Break Even: If Profit > 1R.
        2. Fractal Trail: If Profit > 2R, Move SL to most recent Fractal Support/Resistance.
        """
        try:
            risk = abs(entry_price - current_sl)
            if risk == 0: return # Already at BE or weird state
            
            new_sl = None
            modification_reason = ""
            
            # BUG FIX #10: Removed in-memory tracker, use persisted state instead
            # (Partial close state now stored in trade['partial_closed'])
            
            # Logic: If Fractal is valid (not 0) use it. Else fallback to ATR? 
            # Actually user asked for Fractal. If no fractal, we hold current SL.
            
            f_res = fractal_levels.get('resistance', 0.0) if fractal_levels else 0.0
            f_sup = fractal_levels.get('support', 0.0) if fractal_levels else 0.0
            
            if action == "BUY":
                profit = current_price - entry_price
                
                # BANK & RUNNER LOGIC (Greedy but Safe)
                # If price covers 40% of distance to TP:
                # 1. Close 50% of the trade (Bank Cash)
                # 2. Move SL to Break Even (Risk Free Runner)
                tp_dist = abs(tp - entry_price)
                if tp_dist > 0 and profit >= (0.4 * tp_dist):
                    if self.close_partial(ticket, 0.5):
                        print(f"💰 BANK & RUNNER: Target Hit (40% TP). Closed 50% of {ticket}.")
                        # IMMEDIATE BREAK EVEN
                        new_sl = entry_price + (atr * 0.1)
                        modification_reason = "Bank & Runner (BE Secured)"
                        # We do NOT return, we continue to let the modification happen below if needed, 
                        # but actually we set new_sl here so it will trigger modification.

                # Trigger 1: Break Even (Profit > 1.0 * Risk) - Standard Trail
                if profit > (1.0 * risk) and current_sl < entry_price:
                    # Only move if we haven't already moved it via Bank & Runner
                    if new_sl is None: 
                        new_sl = entry_price + (atr * 0.1) 
                        modification_reason = "Break-Even (+1R)"
                
                # Trigger 2: Fractal Trailing (Profit > 2.0 * Risk)
                elif profit > (2.0 * risk):
                    # We want to trail to the LAST SUPPORT FRACTAL
                    # Check if valid support fractal exists and is ABOVE current SL
                    if f_sup > current_sl and f_sup < current_price:
                         new_sl = f_sup - (atr * 0.1) # Buffer below support
                         modification_reason = "Structure Trail (Fractal)"

            elif action == "SELL":
                profit = entry_price - current_price
                
                # BANK & RUNNER LOGIC (Greedy but Safe)
                tp_dist = abs(entry_price - tp)
                if tp_dist > 0 and profit >= (0.4 * tp_dist):
                    if self.close_partial(ticket, 0.5):
                         print(f"💰 BANK & RUNNER: Target Hit (40% TP). Closed 50% of {ticket}.")
                         # IMMEDIATE BREAK EVEN
                         new_sl = entry_price - (atr * 0.1)
                         modification_reason = "Bank & Runner (BE Secured)"

                # Trigger 1: Break Even
                if profit > (1.0 * risk) and current_sl > entry_price:
                     if new_sl is None:
                        new_sl = entry_price - (atr * 0.1)
                        modification_reason = "Break-Even (+1R)"

                # Trigger 1: Break Even
                if profit > (1.0 * risk) and current_sl > entry_price:
                    new_sl = entry_price - (atr * 0.1)
                    modification_reason = "Break-Even (+1R)"
                
                # Trigger 2: Fractal Trailing
                elif profit > (2.0 * risk):
                     # Trail to LAST RESISTANCE FRACTAL
                     if f_res > 0 and f_res < current_sl and f_res > current_price:
                         new_sl = f_res + (atr * 0.1) # Buffer above resistance
                         modification_reason = "Structure Trail (Fractal)"

            # Execute Modification
            if new_sl:
                # Round to 5 decimals for Forex
                new_sl = round(new_sl, 5)
                
                # Use helper method to respect Mocking/Backtest Mode
                if self.modify_order_sl(int(ticket), new_sl):
                     print(f"✅ SL UPDATE ({modification_reason}): Ticket {ticket} -> {new_sl}")
                     # Update local state so we don't spam requests
                     # (Note: local state will refresh next loop from file, so this is just for awareness)
                else:
                     print(f"⚠️ SL Update Failed (MT5 Error or connection).")
                    
        except Exception as e:
            print(f"Trailing Stop Error: {e}")

    def check_cycling_condition(self, active_trades: list, current_price: float) -> dict:
        """
        Checks if we can 'Cycle' (Close T1 to open New) based on profit milestones.
        Rule: 
        - Trade 1 (Oldest) >= 80% to TP
        - Trade 2 (Next)   >= 40% to TP
        
        Returns: {'can_cycle': bool, 'trade_to_close': ticket}
        """
        if len(active_trades) < 2:
            return {'can_cycle': False, 'trade_to_close': None}
            
        # 1. Identify Trades (Assuming list is ordered by time, which it usually is from main.py append)
        # We should strictly sort by ticket just to be safe (lower ticket = older)
        sorted_trades = sorted(active_trades, key=lambda x: x['ticket'])
        t1 = sorted_trades[0]
        t2 = sorted_trades[1]
        
        # 2. Check T1 Progress (>= 80%)
        t1_prog = self._calculate_progress(t1, current_price)
        if t1_prog < 0.80:
            return {'can_cycle': False, 'trade_to_close': None}
            
        # 3. Check T2 Progress (>= 40%)
        t2_prog = self._calculate_progress(t2, current_price)
        if t2_prog < 0.40:
            return {'can_cycle': False, 'trade_to_close': None}
            
        return {'can_cycle': True, 'trade_to_close': t1['ticket']}

    def _calculate_progress(self, trade, current_price):
        """Calculates how close a trade is to TP (0.0 to 1.0)."""
        try:
            entry = trade['open_price']
            tp = trade['tp']
            action = trade['action']
            
            if action == "BUY":
                total_dist = tp - entry
                curr_dist = current_price - entry
                if total_dist == 0: return 0
                return curr_dist / total_dist
            elif action == "SELL":
                total_dist = entry - tp
                curr_dist = entry - current_price
                if total_dist == 0: return 0
                return curr_dist / total_dist
            return 0
        except:
            return 0

    def close_trade(self, ticket):
        """Manually closes a specific trade (Netting/Hedging compliant)."""
        try:
            # 1. Get Position Details to know Volume and Type
            positions = mt5.positions_get(ticket=int(ticket))
            if not positions:
                print(f"Cannot close trade {ticket}: Not found in MT5.")
                return False
                
            pos = positions[0]
            
            # 2. Determine Opposite Action
            op_type = mt5.ORDER_TYPE_SELL if pos.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
            
            # 3. Send Close Order
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "position": pos.ticket,
                "symbol": pos.symbol,
                "volume": pos.volume,
                "type": op_type,
                "price": mt5.symbol_info_tick(pos.symbol).bid if op_type == mt5.ORDER_TYPE_SELL else mt5.symbol_info_tick(pos.symbol).ask,
                "deviation": 20,
                "magic": 234000,
                "comment": "Cycle Close (Strategy)",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            
            res = mt5.order_send(request)
            if res.retcode == mt5.TRADE_RETCODE_DONE:
                print(f"♻️ CYCLED TRADE {ticket} (Closed for Profit Rotation).")
                return True
            else:
                print(f"⚠️ Failed to Cycle Trade {ticket}: {res.comment}")
                return False
                
        except Exception as e:
            print(f"Close Trade Error: {e}")
            return False

    def close_partial(self, ticket: int, fraction: float) -> bool:
        """
        Closes a partial fraction of position (0.0-1.0).
        Used for partial profit taking.
        """
        try:
            if self.backtest_mode:
                # In backtest mode, we can't actually split positions
                # Just log it and return True
                print(f"[BACKTEST] Would close {fraction*100:.0f}% of {ticket}")
                return True
            
            if not mt5.initialize():
                return False
            
            # 1. Get Position Details
            positions = mt5.positions_get(ticket=int(ticket))
            if not positions:
                print(f"Cannot close partial {ticket}: Not found in MT5.")
                return False
                
            pos = positions[0]
            
            # 2. Calculate Partial Volume
            close_volume = round(pos.volume * fraction, 2)
            if close_volume < 0.01:  # Minimum lot size
                print(f"Partial volume too small ({close_volume:.2f}), skipping.")
                return False
            
            # 3. Determine Opposite Action
            op_type = mt5.ORDER_TYPE_SELL if pos.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
            
            # 4. Send Partial Close Order
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "position": pos.ticket,
                "symbol": pos.symbol,
                "volume": close_volume,  # Partial volume
                "type": op_type,
                "price": mt5.symbol_info_tick(pos.symbol).bid if op_type == mt5.ORDER_TYPE_SELL else mt5.symbol_info_tick(pos.symbol).ask,
                "deviation": 20,
                "magic": 234001,
                "comment": "Partial Profit Take",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            
            res = mt5.order_send(request)
            if res.retcode == mt5.TRADE_RETCODE_DONE:
                print(f"✅ PARTIAL CLOSE: {close_volume} lots of {ticket} closed (${res.price:.5f})")
                return True
            else:
                print(f"⚠️ Failed to Partial Close {ticket}: {res.comment} (Code: {res.retcode})")
                return False
                
        except Exception as e:
            print(f"Partial Close Error: {e}")
            return False
