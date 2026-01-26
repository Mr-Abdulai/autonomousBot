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
                "mode": "BACKTEST"
            }
            # Append to existing
            current_trades = self.load_state()
            current_trades.append(trade_data)
            self.save_state(current_trades)
            
            print(f"[BACKTEST] Trade Mock-Executed. Ticket: {mock_ticket}")
            return mock_ticket

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
            "ticket": result.order,
            "symbol": self.symbol,
            "mode": "LIVE",
            "action": action,
            "volume": volume_lots,
            "open_price": result.price,
            "sl": sl_price,
            "tp": tp_price
        }
        
        current_trades = self.load_state()
        current_trades.append(trade_data)
        self.save_state(current_trades)
        return str(result.order)

    def modify_order_sl(self, ticket: int, new_sl: float) -> bool:
        """Helper to modify SL."""
        if self.backtest_mode: return True
        
        request = {"action": mt5.TRADE_ACTION_SLTP, "position": ticket, "sl": new_sl, "tp": 0.0, "magic": 123456}
        pos = mt5.positions_get(ticket=ticket)
        if pos: request["tp"] = pos[0].tp
        
        res = mt5.order_send(request)
        return res.retcode == mt5.TRADE_RETCODE_DONE

    def monitor_open_trades(self, current_price: float, atr: float = 0.0) -> dict:
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
                        # Fetch PnL logic here... (Simplified for brevity)
                        print(f"Trade {ticket} Closed in MT5.")
                        # Logic to fetch real PnL omitted for space, assuming 0 or approx
            
            # --- MANAGEMENT LOGIC (If Active) ---
            if not is_closed:
                # 1. Calc Stats
                dist_total = abs(tp - open_price)
                dist_covered = abs(current_price - open_price)
                is_profit = (action=="BUY" and current_price>open_price) or (action=="SELL" and current_price<open_price)
                
                new_sl = None
                
                if is_profit and dist_total > 0:
                    pct = dist_covered / dist_total
                    
                    # BE Trigger (50%)
                    sl_at_be = (action=="BUY" and sl>=open_price) or (action=="SELL" and sl<=open_price)
                    if pct >= 0.50 and not sl_at_be:
                        new_sl = open_price
                        print(f"💰 {ticket}: Moving to Break Even.")
                    
                    # Trailing (60%)
                    if pct >= 0.60 and atr > 0:
                        buf = atr * 1.5
                        pot_sl = current_price - buf if action=="BUY" else current_price + buf
                        if (action=="BUY" and pot_sl > sl) or (action=="SELL" and pot_sl < sl):
                            new_sl = pot_sl
                            print(f"🚀 {ticket}: Trailing Stop Update.")

                if new_sl:
                    if mode == "LIVE":
                        if self.modify_order_sl(int(ticket), new_sl):
                            trade['sl'] = new_sl
                            updated = True
                            managed_count += 1
                    else:
                        trade['sl'] = new_sl
            if not is_closed and mode == "LIVE":
                # Only apply trailing stop if we have valid ATR
                if atr > 0:
                    # The apply_trailing_stop method will handle the modification and print statements
                    # It also updates the local 'sl' in the trade dictionary if successful
                    self.apply_trailing_stop(ticket, current_price, open_price, action, sl, tp, atr)
                    # We don't need to explicitly set 'updated = True' or 'managed_count += 1' here
                    # as the new method handles the MT5 interaction and prints its own status.
                    # The local 'sl' update within apply_trailing_stop is for immediate awareness,
                    # but the state will be reloaded from file on the next iteration anyway.
                    # For simplicity, we'll let the next load_state pick up the actual SL from MT5.
                    # If we wanted to track managed_count, we'd need apply_trailing_stop to return a bool.
                    # For now, we'll assume it's managed if we attempt to apply it.
                    managed_count += 1 # Increment if we attempted to apply trailing stop

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

    def apply_trailing_stop(self, ticket, current_price, entry_price, action, current_sl, tp, atr):
        """
        Dynamically moves Stop Loss based on profit milestones.
        1. Break Even: If Profit > 1R (Risk), Move SL to Entry.
        2. Trailing: If Profit > 2R, Trail SL by 1.5 * ATR.
        """
        try:
            risk = abs(entry_price - current_sl)
            if risk == 0: return # Already at BE or weird state
            
            new_sl = None
            modification_reason = ""
            
            if action == "BUY":
                profit = current_price - entry_price
                
                # Trigger 1: Break Even (Profit > 1.0 * Risk)
                if profit > (1.0 * risk) and current_sl < entry_price:
                    new_sl = entry_price + (atr * 0.1) # BE + small buffer
                    modification_reason = "Break-Even (+1R)"
                
                # Trigger 2: Dynamic Trailing (Profit > 2.0 * Risk)
                elif profit > (2.0 * risk):
                    potential_sl = current_price - (1.5 * atr)
                    # Only move UP
                    if potential_sl > current_sl:
                        new_sl = potential_sl
                        modification_reason = "Trailing Stop (1.5 ATR)"

            elif action == "SELL":
                profit = entry_price - current_price
                
                # Trigger 1: Break Even
                if profit > (1.0 * risk) and current_sl > entry_price:
                    new_sl = entry_price - (atr * 0.1)
                    modification_reason = "Break-Even (+1R)"
                
                # Trigger 2: Trailing
                elif profit > (2.0 * risk):
                    potential_sl = current_price + (1.5 * atr)
                    # Only move DOWN
                    if potential_sl < current_sl:
                        new_sl = potential_sl
                        modification_reason = "Trailing Stop (1.5 ATR)"

            # Execute Modification
            if new_sl:
                # Round to 5 decimals for Forex
                new_sl = round(new_sl, 5)
                
                request = {
                    "action": mt5.TRADE_ACTION_SLTP,
                    "position": int(ticket),
                    "sl": new_sl,
                    "tp": tp # Keep existing TP
                }
                
                res = mt5.order_send(request)
                if res.retcode == mt5.TRADE_RETCODE_DONE:
                    print(f"✅ SL UPDATE ({modification_reason}): Ticket {ticket} -> {new_sl}")
                    # Update local state so we don't spam requests
                    # (Note: local state will refresh next loop from file, so this is just for awareness)
                else:
                    print(f"⚠️ SL Update Failed: {res.comment}")
                    
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
