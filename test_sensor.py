from app.market_sensor import MarketSensor
import MetaTrader5 as mt5

if __name__ == "__main__":
    s = MarketSensor()
    if s.initialize():
        print(s.get_market_summary())
        mt5.shutdown()
    else:
        print("Failed to init")
