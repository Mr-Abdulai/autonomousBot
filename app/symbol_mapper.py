"""
Symbol Mapping Utility for Multi-Broker Support
Handles broker-specific symbol naming conventions
"""

class SymbolMapper:
    """
    PHASE 5C: Broker Symbol Mapping
    Maps standard symbols to broker-specific formats
    Critical for multi-broker compatibility
    """
    
    # Broker-specific suffix mappings
    BROKER_SUFFIXES = {
        "exness": "m",          # EURUSDm
        "icmarkets": ".r",      # EURUSD.r
        "pepperstone": "",      # EURUSD (no suffix)
        "oanda": "_",           # EUR_USD (underscore format)
        "fxcm": "",             # EURUSD
        "xm": "",               # EURUSD
        "tickmill": ".pro",     # EURUSD.pro
        "roboforex": ".ecn",    # EURUSD.ecn
        "alpari": "-sb",        # EURUSD-sb
    }
    
    # Standard symbol list (normalized)
    STANDARD_SYMBOLS = [
        "EURUSD", "GBPUSD", "USDJPY", "USDCHF",
        "AUDUSD", "USDCAD", "NZDUSD",
        "EURGBP", "EURJPY", "GBPJPY",
        "XAUUSD", "XAGUSD",  # Gold, Silver
        "US30", "NAS100", "SPX500"  # Indices
    ]
    
    def __init__(self, broker: str = "exness"):
        """
        Initialize with broker name
        broker: str - lowercase broker name (e.g., 'exness', 'icmarkets')
        """
        self.broker = broker.lower()
        self.suffix = self.BROKER_SUFFIXES.get(self.broker, "")
    
    def to_broker_symbol(self, standard_symbol: str) -> str:
        """
        Convert standard symbol to broker-specific format
        Example: EURUSD -> EURUSDm (Exness)
        """
        standard_symbol = standard_symbol.upper()
        
        # Special handling for OANDA (uses underscore)
        if self.broker == "oanda":
            if len(standard_symbol) == 6:  # Forex pair
                return f"{standard_symbol[:3]}_{standard_symbol[3:]}"
            return standard_symbol
        
        # Standard suffix append
        return f"{standard_symbol}{self.suffix}"
    
    def to_standard_symbol(self, broker_symbol: str) -> str:
        """
        Convert broker-specific symbol to standard format
        Example: EURUSDm -> EURUSD, EUR_USD -> EURUSD
        """
        broker_symbol = broker_symbol.upper()
        
        # Remove underscore (OANDA format)
        if "_" in broker_symbol:
            broker_symbol = broker_symbol.replace("_", "")
        
        # Remove known suffixes
        for suffix in self.BROKER_SUFFIXES.values():
            if suffix and broker_symbol.endswith(suffix.upper()):
                broker_symbol = broker_symbol[:-len(suffix)]
                break
        
        return broker_symbol
    
    def validate_symbol(self, symbol: str) -> bool:
        """
        Check if symbol is valid (exists in standard list)
        """
        standard = self.to_standard_symbol(symbol)
        return standard in self.STANDARD_SYMBOLS
    
    def get_available_symbols(self) -> list:
        """
        Returns list of all symbols in broker format
        """
        return [self.to_broker_symbol(sym) for sym in self.STANDARD_SYMBOLS]
    
    @staticmethod
    def auto_detect_broker(sample_symbol: str) -> str:
        """
        Attempt to detect broker from symbol format
        Example: EURUSDm -> 'exness'
        """
        sample_symbol = sample_symbol.upper()
        
        # Check for underscore (OANDA)
        if "_" in sample_symbol:
            return "oanda"
        
        # Check suffixes
        for broker, suffix in SymbolMapper.BROKER_SUFFIXES.items():
            if suffix and sample_symbol.endswith(suffix.upper()):
                return broker
        
        # Default to no suffix brokers
        return "pepperstone"  # or "fxcm", "xm" - clean format


# Usage examples
if __name__ == "__main__":
    # Test Exness mapping
    exness_mapper = SymbolMapper(broker="exness")
    print(f"Standard EURUSD -> Exness: {exness_mapper.to_broker_symbol('EURUSD')}")  # EURUSDm
    print(f"Exness EURUSDm -> Standard: {exness_mapper.to_standard_symbol('EURUSDm')}")  # EURUSD
    
    # Test IC Markets mapping
    ic_mapper = SymbolMapper(broker="icmarkets")
    print(f"Standard GBPUSD -> IC Markets: {ic_mapper.to_broker_symbol('GBPUSD')}")  # GBPUSD.r
    
    # Test OANDA mapping
    oanda_mapper = SymbolMapper(broker="oanda")
    print(f"Standard USDJPY -> OANDA: {oanda_mapper.to_broker_symbol('USDJPY')}")  # USD_JPY
    print(f"OANDA EUR_USD -> Standard: {oanda_mapper.to_standard_symbol('EUR_USD')}")  # EURUSD
    
    # Auto-detect broker
    detected = SymbolMapper.auto_detect_broker("EURUSDm")
    print(f"Auto-detected broker for 'EURUSDm': {detected}")  # exness
