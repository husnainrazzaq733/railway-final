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
        print(f"Error fetching forex price via yfinance for {symbol}: {e}")
        
    # Fallback 1: Raw Yahoo Finance API
    try:
        url = f"https://query2.finance.yahoo.com/v8/finance/chart/{symbol}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get('chart', {}).get('result'):
                price = data['chart']['result'][0]['meta']['regularMarketPrice']
                return float(price)
    except Exception as e:
        print(f"Error fetching forex price via Yahoo API for {symbol}: {e}")


    return None

def get_price(symbol):
    """
    Attempt to fetch price as crypto. If that fails, attempt as forex.
    """
    symbol_clean = symbol.upper().replace("/", "").replace("-", "")
    
    if symbol_clean in ['GOLD', 'XAUUSD', 'XAU', 'GCF', 'GC=F']:
        # Fetch actual Spot Gold via YFinance (matches MT5)
        price = get_forex_price('XAUUSD=X')
        if price is not None:
            return price, 'forex', 'GOLD'
            
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

def get_pivot_points(symbol, is_crypto=True, is_gold=False, is_swap=False):
    """
    Fetch 24h High/Low and calculate Pivot, R1, R2, S1, S2
    """
    try:
        high = None
        low = None
        close = None
        
        if is_gold:
            url = "https://api.bybit.com/v5/market/tickers?category=linear&symbol=XAUUSDT"
            res = requests.get(url, timeout=10)
            if res.status_code == 200:
                data = res.json()
                if data.get('retCode') == 0 and data.get('result', {}).get('list'):
                    tick = data['result']['list'][0]
                    high = float(tick['highPrice24h'])
                    low = float(tick['lowPrice24h'])
                    close = float(tick['lastPrice'])
        elif is_crypto:
            if is_swap:
                url = f"https://fapi.binance.com/fapi/v1/ticker/24hr?symbol={symbol}"
            else:
                url = f"https://api.binance.com/api/v3/ticker/24hr?symbol={symbol}"
            res = requests.get(url, timeout=10)
            if res.status_code == 200:
                data = res.json()
                if 'highPrice' in data and 'lowPrice' in data:
                    high = float(data['highPrice'])
                    low = float(data['lowPrice'])
                    close = float(data['lastPrice'])
                    
        if high and low and close:
            p = (high + low + close) / 3
            r1 = (p * 2) - low
            s1 = (p * 2) - high
            r2 = p + (high - low)
            s2 = p - (high - low)
            
            # Format precision based on general price
            decimals = 2 if close > 10 else 4
            
            return {
                'p': round(p, decimals),
                'r1': round(r1, decimals),
                's1': round(s1, decimals),
                'r2': round(r2, decimals),
                's2': round(s2, decimals)
            }
    except Exception as e:
        print(f"Error calculating pivots for {symbol}: {e}")
        
    return None
