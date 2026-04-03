import sys
import os
import MetaTrader5 as mt5

def test_trade():
    print("Testing MT5 Connection...")
    # Get MT5 credentials from .env
    from dotenv import load_dotenv
    load_dotenv()
    
    login = int(os.getenv("MT5_LOGIN"))
    password = os.getenv("MT5_PASSWORD")
    server = os.getenv("MT5_SERVER")
    symbol = os.getenv("SYMBOL", "XAUUSD")
    
    if not mt5.initialize(login=login, password=password, server=server):
        print(f"Failed to connect to MT5. Error: {mt5.last_error()}")
        return False
    
    print(f"Connected to MT5! Account Info: {mt5.account_info()}")
    print(f"Testing Symbol: {symbol}")
    
    # Check if symbol is available
    if not mt5.symbol_select(symbol, True):
        print(f"Failed to select {symbol} in Market Watch.")
        mt5.shutdown()
        return False
    
    # Try placing a minimal buy
    tick = mt5.symbol_info_tick(symbol)
    if not tick:
        print(f"Failed to get tick for {symbol}. Check if symbol is correct/available.")
        mt5.shutdown()
        return False
        
    price = tick.ask
    print(f"Current Ask Price: {price}")
    
    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": 0.01,
        "type": mt5.ORDER_TYPE_BUY,
        "price": price,
        "sl": price * 0.99,  # 1% below ask
        "tp": price * 1.01,  # 1% above ask
        "deviation": 20,
        "magic": 999999,
        "comment": "Test Connection",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }
    
    print("Sending order...")
    result = mt5.order_send(request)
    
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        print(f"Order failed with retcode: {result.retcode}")
        print(f"Result details: {result}")
        mt5.shutdown()
        return False
        
    print(f"Order SUCCESS! Ticket: {result.order}")
    mt5.shutdown()
    return True

if __name__ == "__main__":
    test_trade()
