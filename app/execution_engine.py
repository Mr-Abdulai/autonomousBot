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
                # Apply Smart Trailing (updates trade dict in place)
                # Uses ATR for validation but purely Structural (Fractal) targets if available
                self.apply_trailing_stop(trade, current_price, atr, fractal_levels)
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

    def apply_trailing_stop(self, trade, current_price, atr, fractal_levels=None, gamma_state=None):
        """
        Dynamically moves Stop Loss based on profit milestones.
        Updates 'trade' dictionary in-place if successful.
        """
        ticket = trade.get('ticket')
        entry_price = trade.get('open_price')
        action = trade.get('action')
        current_sl = trade.get('sl')
        tp = trade.get('tp')
        volume = trade.get('volume', 0.01)
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
            
            # PHASE 92: GAMMA WALL DEFENSE 
            # If we are near a Gamma Wall, Trailing stops must squeeze tighter!
            # Default buffer is (atr * 0.1). Gamma wall squashes it by 60%.
            gamma_ts_multiplier = gamma_state.get('ts_multiplier', 1.0) if gamma_state else 1.0
            ts_buffer = (atr * 0.1) * gamma_ts_multiplier
            
            if action == "BUY":
                profit = current_price - entry_price
                
                # Trigger 1: Break Even (Profit > 1.0 * Risk) - Standard Trail
                if profit > (1.0 * risk) and current_sl < entry_price:
                    new_sl = entry_price + ts_buffer 
                    modification_reason = "Break-Even (+1R)"
                
                # Trigger 2: Fractal Trailing (Profit > 2.0 * Risk)
                elif profit > (2.0 * risk):
                    # We want to trail to the LAST SUPPORT FRACTAL
                    # Check if valid support fractal exists and is ABOVE current SL
                    if f_sup > current_sl and f_sup < current_price:
                         new_sl = f_sup - ts_buffer # Buffer below support
                         modification_reason = "Structure Trail (Fractal)"

            elif action == "SELL":
                profit = entry_price - current_price
                
                # Trigger 1: Break Even
                if profit > (1.0 * risk) and current_sl > entry_price:
                    new_sl = entry_price - ts_buffer
                    modification_reason = "Break-Even (+1R)"
                
                # Trigger 2: Fractal Trailing
                elif profit > (2.0 * risk):
                     # Trail to LAST RESISTANCE FRACTAL
                     if f_res > 0 and f_res < current_sl and f_res > current_price:
                         new_sl = f_res + ts_buffer # Buffer above resistance
                         modification_reason = "Structure Trail (Fractal)"

            # Execute Modification
            if new_sl:
                # Round to 5 decimals for Forex
                new_sl = round(new_sl, 5)
                
                # Use helper method to respect Mocking/Backtest Mode
                if self.modify_order_sl(int(ticket), new_sl):
                     print(f"✅ SL UPDATE ({modification_reason}): Ticket {ticket} -> {new_sl}")
                     # Update local state so we don't spam requests
                     trade['sl'] = new_sl  # PERSIST CHANGE
                else:
                     print(f"⚠️ SL Update Failed (MT5 Error or connection).")
                    
        except Exception as e:
            print(f"Trailing Stop Error: {e}")

    def check_pyramiding_condition(self, active_trades: list, current_price: float) -> dict:
        """
        ULTIMATE GOLD STRATEGY 3: Dynamic Grid Scaling (The Pyramiding Protocol)
        Checks if we can add a new position to an already winning trend.
        Rule: 
        - Find a trade that is significantly in profit (>1.5R)
        - The trade MUST have its Stop Loss already moved to Break-Even or better (Risk-Free).
        - Ensure we haven't already pyramided off this specific trade ticket.
        
        Returns: {'can_pyramid': bool, 'base_trade': trade_dict, 'action_to_take': str}
        """
        if not active_trades:
            return {'can_pyramid': False, 'base_trade': None, 'action_to_take': None}
            
        for trade in active_trades:
            # Check if we already pyramided off this trade
            if trade.get('pyramided', False):
                continue
                
            entry = trade['open_price']
            action = trade['action']
            sl = trade['sl']
            
            # Prevent Div/0 on weird trades
            if sl == entry: continue 
            
            initial_risk = abs(entry - sl)
            
            # Risk-Free Check & Profit Milestone
            if action == 'BUY':
                profit = current_price - entry
                is_risk_free = sl > entry
                if is_risk_free and profit > (initial_risk * 1.5):
                    return {'can_pyramid': True, 'base_trade': trade, 'action_to_take': 'BUY'}
                    
            elif action == 'SELL':
                profit = entry - current_price
                is_risk_free = sl < entry
                if is_risk_free and profit > (initial_risk * 1.5):
                    return {'can_pyramid': True, 'base_trade': trade, 'action_to_take': 'SELL'}
                    
        return {'can_pyramid': False, 'base_trade': None, 'action_to_take': None}

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
                
                # BUG FIX: MT5 Ticket Mutation (Hedging Mode generates new ticket)
                import time
                time.sleep(0.1) # Brief pause for MT5 to execute position shift
                
                updated_positions = mt5.positions_get(symbol=pos.symbol)
                new_ticket_id = ticket
                if updated_positions:
                    # Look for old ticket still existing (Netting Mode)
                    for p in updated_positions:
                        if str(p.ticket) == str(ticket):
                            new_ticket_id = ticket
                            break
                        # Look for replacement ticket via matching Magic + Remaining Volume (Hedging Mode)
                        elif p.magic == pos.magic and abs(p.volume - (pos.volume - close_volume)) < 0.001:
                            new_ticket_id = p.ticket
                            break
                            
                if str(new_ticket_id) != str(ticket):
                    print(f"🔄 Ticket Mutated on Partial Close: {ticket} -> {new_ticket_id}")
                    states = self.load_state()
                    for t in states:
                        if str(t['ticket']) == str(ticket):
                            t['ticket'] = str(new_ticket_id)
                    self.save_state(states)
                    
                return True
            else:
                print(f"⚠️ Failed to Partial Close {ticket}: {res.comment} (Code: {res.retcode})")
                return False
                
        except Exception as e:
            print(f"Partial Close Error: {e}")
            return False

    def _mark_trade_pyramided(self, ticket) -> bool:
        """
        Marks a specific trade in state as having already spawned a pyramid position.
        Prevents infinite scaling loops off the same base trade.
        """
        try:
            states = self.load_state()
            found = False
            for t in states:
                if str(t['ticket']) == str(ticket):
                    t['pyramided'] = True
                    found = True
                    break
            
            if found:
                self.save_state(states)
                return True
            return False
            
        except Exception as e:
            print(f"Pyramid Marking Error: {e}")
            return False
