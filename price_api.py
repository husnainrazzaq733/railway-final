import requests
import yfinance as yf

def get_swap_price(symbol):
    """
    Fetch Swap (Futures) price from Binance API.
    """
    try:
        url = f"https://fapi.binance.com/fapi/v1/ticker/price?symbol={symbol}"
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            if 'price' in data:
                return float(data['price'])
    except Exception as e:
        print(f"Error fetching swap price for {symbol}: {e}")
    return None

def get_spot_price(symbol):
    """
    Fetch Spot price from Binance API.
    """
    try:
        url = f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}"
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            if 'price' in data:
                return float(data['price'])
    except Exception as e:
        print(f"Error fetching spot price for {symbol}: {e}")
    return None

def get_forex_price(symbol):
    """
    Fetch forex price from yfinance.
    Ensure symbol has =X at the end, e.g., EURUSD=X.
    """
    try:
        ticker = yf.Ticker(symbol)
        # fast_info is efficient for current price
        price = ticker.fast_info.last_price
        return float(price)
    except Exception as e:
        print(f"Error fetching forex price for {symbol}: {e}")
        return None

def get_price(symbol):
    """
    Attempt to fetch price as crypto. If that fails, attempt as forex.
    """
    symbol_clean = symbol.upper().replace("/", "").replace("-", "")
    
    # 1. Try Binance (Swap then Spot)
    # Most user input like "BTC" means "BTCUSDT" for price checks
    binance_symbol = symbol_clean
    if not binance_symbol.endswith("USDT") and not binance_symbol.endswith("BUSD") and not binance_symbol.endswith("BTC"):
        binance_symbol = symbol_clean + "USDT"
        
    price = get_swap_price(binance_symbol)
    if price is None:
        price = get_spot_price(binance_symbol)
        
    if price is not None:
        return price, 'crypto', binance_symbol

    # Try original symbol on binance if it might be a valid pair already
    price = get_swap_price(symbol_clean)
    if price is None:
         price = get_spot_price(symbol_clean)
         
    if price is not None:
         return price, 'crypto', symbol_clean
         
    # 2. Try yfinance (forex/stocks)
    # yfinance forex pairs usually end with =X, commodities with =F
    if "=" in symbol_clean:
        yf_symbol = symbol_clean
    elif not symbol_clean.endswith("=X"):
        yf_symbol = symbol_clean + "=X"
    else:
        yf_symbol = symbol_clean
        
    price = get_forex_price(yf_symbol)
    if price is not None:
        return price, 'forex', yf_symbol
        
    # If the default =X failed, also try the exact given symbol just in case
    if "=" not in symbol_clean:
        price = get_forex_price(symbol_clean)
        if price is not None:
            return price, 'forex', symbol_clean

    return None, None, None
