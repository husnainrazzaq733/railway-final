import requests
import concurrent.futures

def calculate_rsi(closes, period=14):
    if len(closes) < period + 1:
        return None
    
    # Calculate daily returns
    deltas = [closes[i] - closes[i-1] for i in range(1, len(closes))]
    
    # Separate gains and losses
    gains = [d if d > 0 else 0 for d in deltas]
    losses = [-d if d < 0 else 0 for d in deltas]
    
    # Calculate initial average gain and loss
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    
    if avg_loss == 0:
         return 100.0
         
    # Calculate RSI using exponential moving average (Wilder's Smoothing)
    for i in range(period, len(deltas)):
        avg_gain = ((avg_gain * (period - 1)) + gains[i]) / period
        avg_loss = ((avg_loss * (period - 1)) + losses[i]) / period
        
    if avg_loss == 0:
        return 100.0
        
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return round(rsi, 2)

def fetch_klines_and_rsi(symbol, interval, market_type='spot'):
    """
    Fetch klines from Binance API and compute RSI for the given interval.
    """
    try:
        if market_type == 'swap':
            base_url = "https://fapi.binance.com/fapi/v1"
        else:
            base_url = "https://api.binance.com/api/v3"
            
        url = f"{base_url}/klines?symbol={symbol}&interval={interval}&limit=100"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            # Binance klines format: [ [Open_time, Open, High, Low, Close, Volume, Close_time, ...], ...]
            closes = [float(candle[4]) for candle in data]
            rsi_value = calculate_rsi(closes)
            return interval, rsi_value
    except Exception as e:
        print(f"Error fetching {interval} RSI for {symbol}: {e}")
    return interval, None

def get_crypto_rsi(symbol, market_type='spot'):
    """
    Get RSI for 15m, 1h, 4h, and 1D for a given symbol using multithreading.
    Returns a dictionary e.g. {'15m': 34.5, '1h': 45.2, ...}
    """
    # Fix symbol base if needed (like BTC -> BTCUSDT)
    symbol_clean = symbol.upper().replace("/", "").replace("-", "")
    if symbol_clean == "BTC":
        symbol_clean = "BTCUSDT"
    elif not symbol_clean.endswith("USDT") and not symbol_clean.endswith("BUSD") and not symbol_clean.endswith("BTC") and not symbol_clean.endswith("USDC"):
        symbol_clean += "USDT"
        
    intervals = ['15m', '1h', '4h', '1d']
    rsi_results = {}
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(fetch_klines_and_rsi, symbol_clean, interval, market_type) for interval in intervals]
        for future in concurrent.futures.as_completed(futures):
            interval, rsi_val = future.result()
            rsi_results[interval] = rsi_val
            
    return symbol_clean, rsi_results

def get_tradable_usdt_coins(market_type='spot'):
    tradable = set()
    try:
        url = "https://fapi.binance.com/fapi/v1/exchangeInfo" if market_type == 'swap' else "https://api.binance.com/api/v3/exchangeInfo"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            for symbol_info in data.get('symbols', []):
                sym = symbol_info.get('symbol', '')
                status = symbol_info.get('status')
                
                if market_type == 'swap':
                    contract_type = symbol_info.get('contractType')
                    if status == 'TRADING' and contract_type == 'PERPETUAL':
                        tradable.add(sym)
                else:
                    if status == 'TRADING':
                        tradable.add(sym)
    except Exception as e:
        print(f"Error fetching exchange info: {e}")
    return tradable

def get_top_usdt_coins(limit=300, market_type='spot'):
    tradable_symbols = get_tradable_usdt_coins(market_type)
    url = "https://fapi.binance.com/fapi/v1/ticker/24hr" if market_type == 'swap' else "https://api.binance.com/api/v3/ticker/24hr"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            valid_coins = []
            for item in data:
                sym = item['symbol']
                # Skip if not in our currently tradable set (if we managed to fetch it)
                if tradable_symbols and sym not in tradable_symbols:
                    continue
                    
                if sym.endswith("USDT") and "UPUSDT" not in sym and "DOWNUSDT" not in sym and "BULL" not in sym and "BEAR" not in sym and sym not in ["USDCUSDT", "FDUSDUSDT", "TUSDUSDT", "BUSDUSDT", "EURUSDT"]:
                    vol_key = 'quoteVolume'
                    valid_coins.append({
                        'symbol': sym,
                        'volume': float(item.get(vol_key, 0))
                    })
            valid_coins.sort(key=lambda x: x['volume'], reverse=True)
            return [x['symbol'] for x in valid_coins[:limit]]
    except Exception as e:
        print(f"Error fetching top coins: {e}")
    # Fallback to avoid breaking
    return ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "ADAUSDT", "DOGEUSDT"]

def check_single_coin_rsi(symbol, interval, market_type):
    base_url = "https://fapi.binance.com/fapi/v1" if market_type == 'swap' else "https://api.binance.com/api/v3"
    url = f"{base_url}/klines?symbol={symbol}&interval={interval}&limit=50"
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            closes = [float(candle[4]) for candle in data]
            rsi_value = calculate_rsi(closes)
            if rsi_value is not None:
                if rsi_value <= 30:
                    return symbol, rsi_value, 'buy'
                elif rsi_value >= 70:
                    return symbol, rsi_value, 'sell'
    except:
        pass
    return None, None, None

def scan_market_rsi_both(market_type, interval, limit=300):
    coins = get_top_usdt_coins(limit, market_type)
    buy_results = []
    sell_results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
        futures = [executor.submit(check_single_coin_rsi, coin, interval, market_type) for coin in coins]
        for future in concurrent.futures.as_completed(futures):
            sym, rsi_val, action = future.result()
            if sym and rsi_val:
                if action == 'buy':
                    buy_results.append((sym, rsi_val))
                elif action == 'sell':
                    sell_results.append((sym, rsi_val))
                
    buy_results.sort(key=lambda x: x[1]) # Lowest first
    sell_results.sort(key=lambda x: x[1], reverse=True) # Highest first
        
    return buy_results, sell_results
