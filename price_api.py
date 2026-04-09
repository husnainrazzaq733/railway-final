import requests
import yfinance as yf
import os

# ─────────────────────────────────────────────
#  GoldAPI.io — Primary Gold Price Source
# ─────────────────────────────────────────────
_GOLDAPI_KEY = os.environ.get("GOLDAPI_KEY", "goldapi-1bfp1smnqr9qyd-io")
_goldapi_exhausted = False   # becomes True when 429 received → skip until restart

def get_gold_price_goldapi():
    """
    Fetch real Spot Gold price from GoldAPI.io.
    Returns (price, high, low) or (None, None, None) on failure.
    Sets _goldapi_exhausted=True if rate-limit (429) is hit so
    subsequent calls skip this source automatically.
    """
    global _goldapi_exhausted
    if _goldapi_exhausted:
        return None, None, None

    try:
        url = "https://www.goldapi.io/api/XAU/USD"
        headers = {
            "x-access-token": _GOLDAPI_KEY,
            "Content-Type": "application/json"
        }
        response = requests.get(url, headers=headers, timeout=8)

        if response.status_code == 429:
            print("⚠️ GoldAPI.io rate limit reached — switching to fallback sources.")
            _goldapi_exhausted = True
            return None, None, None

        if response.status_code == 200:
            data = response.json()
            price = data.get('price')
            high  = data.get('high_price')
            low   = data.get('low_price')
            if price:
                return float(price), (float(high) if high else None), (float(low) if low else None)
    except Exception as e:
        print(f"Error fetching Gold via GoldAPI.io: {e}")

    return None, None, None


# ─────────────────────────────────────────────
#  Binance — Crypto prices
# ─────────────────────────────────────────────
def get_swap_price(symbol):
    """Fetch Swap (Futures) price from Binance API."""
    try:
        url = f"https://fapi.binance.com/fapi/v1/ticker/price?symbol={symbol}"
        response = requests.get(url, timeout=8)
        if response.status_code == 200:
            data = response.json()
            if 'price' in data:
                return float(data['price'])
    except Exception as e:
        print(f"Error fetching swap price for {symbol}: {e}")
    return None

def get_spot_price(symbol):
    """Fetch Spot price from Binance API."""
    try:
        url = f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}"
        response = requests.get(url, timeout=8)
        if response.status_code == 200:
            data = response.json()
            if 'price' in data:
                return float(data['price'])
    except Exception as e:
        print(f"Error fetching spot price for {symbol}: {e}")
    return None


# ─────────────────────────────────────────────
#  yFinance + Yahoo Raw + Bybit — Forex / fallback
# ─────────────────────────────────────────────
def get_forex_price(symbol):
    """
    Fetch forex price from yfinance.
    Ensure symbol has =X at the end, e.g., EURUSD=X.
    """
    try:
        ticker = yf.Ticker(symbol)
        price = ticker.fast_info.last_price
        return float(price)
    except Exception as e:
        print(f"Error fetching forex price via yfinance for {symbol}: {e}")

    # Fallback: Raw Yahoo Finance API
    try:
        url = f"https://query2.finance.yahoo.com/v8/finance/chart/{symbol}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get('chart', {}).get('result'):
                price = data['chart']['result'][0]['meta']['regularMarketPrice']
                return float(price)
    except Exception as e:
        print(f"Error fetching forex price via Yahoo API for {symbol}: {e}")

    # Last resort for Gold: Bybit Perpetual
    if symbol in ['XAUUSD=X', 'GC=F', 'GOLD']:
        try:
            url = "https://api.bybit.com/v5/market/tickers?category=linear&symbol=XAUUSDT"
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get('retCode') == 0 and data.get('result', {}).get('list'):
                    price = data['result']['list'][0]['lastPrice']
                    return float(price)
        except Exception as e:
            print(f"Error fetching Gold via Bybit API for {symbol}: {e}")

    return None

def get_price(symbol):
    """
    Attempt to fetch price. Gold uses GoldAPI.io (primary) then yFinance fallback.
    Crypto uses Binance. Forex uses yFinance.
    """
    symbol_clean = symbol.upper().replace("/", "").replace("-", "")

    # ── GOLD: GoldAPI.io → yFinance → Bybit ──────────────────────
    if symbol_clean in ['GOLD', 'XAUUSD', 'XAU', 'GCF', 'GC=F', 'XAUUSDX']:
        # 1. Try GoldAPI.io (primary)
        price, _, _ = get_gold_price_goldapi()
        if price is not None:
            print(f"✅ Gold price from GoldAPI.io: {price}")
            return price, 'forex', 'GOLD'
        # 2. Fallback: yFinance
        price = get_forex_price('XAUUSD=X')
        if price is not None:
            print(f"⚠️ Gold price from yFinance fallback: {price}")
            return price, 'forex', 'GOLD'
        return None, None, None

    # ── CRYPTO: Binance Swap → Spot ──────────────────────────────
    binance_symbol = symbol_clean
    if not binance_symbol.endswith("USDT") and not binance_symbol.endswith("BUSD") and not binance_symbol.endswith("BTC"):
        binance_symbol = symbol_clean + "USDT"

    price = get_swap_price(binance_symbol)
    if price is None:
        price = get_spot_price(binance_symbol)
    if price is not None:
        return price, 'crypto', binance_symbol

    # Try exact symbol on Binance
    price = get_swap_price(symbol_clean)
    if price is None:
        price = get_spot_price(symbol_clean)
    if price is not None:
        return price, 'crypto', symbol_clean

    # ── FOREX: yFinance ──────────────────────────────────────────
    if "=" in symbol_clean:
        yf_symbol = symbol_clean
    elif not symbol_clean.endswith("=X"):
        yf_symbol = symbol_clean + "=X"
    else:
        yf_symbol = symbol_clean

    price = get_forex_price(yf_symbol)
    if price is not None:
        return price, 'forex', yf_symbol

    if "=" not in symbol_clean:
        price = get_forex_price(symbol_clean)
        if price is not None:
            return price, 'forex', symbol_clean

    return None, None, None

def get_pivot_points(symbol, is_crypto=True, is_gold=False, is_swap=False):
    """
    Fetch 24h High/Low and calculate Pivot, R1, R2, S1, S2.
    Gold: GoldAPI.io (primary) → Bybit fallback.
    Crypto: Binance 24hr ticker.
    """
    try:
        high = None
        low  = None
        close = None

        if is_gold:
            # ── GoldAPI.io (primary) ──────────────────────────────
            price, api_high, api_low = get_gold_price_goldapi()
            if price and api_high and api_low:
                high  = api_high
                low   = api_low
                close = price
                print("✅ Gold pivots from GoldAPI.io")

            # ── Bybit fallback ────────────────────────────────────
            if not (high and low and close):
                url = "https://api.bybit.com/v5/market/tickers?category=linear&symbol=XAUUSDT"
                res = requests.get(url, timeout=10)
                if res.status_code == 200:
                    data = res.json()
                    if data.get('retCode') == 0 and data.get('result', {}).get('list'):
                        tick  = data['result']['list'][0]
                        high  = float(tick['highPrice24h'])
                        low   = float(tick['lowPrice24h'])
                        close = float(tick['lastPrice'])
                        print("⚠️ Gold pivots from Bybit fallback")

        elif is_crypto:
            if is_swap:
                url = f"https://fapi.binance.com/fapi/v1/ticker/24hr?symbol={symbol}"
            else:
                url = f"https://api.binance.com/api/v3/ticker/24hr?symbol={symbol}"
            res = requests.get(url, timeout=10)
            if res.status_code == 200:
                data = res.json()
                if 'highPrice' in data and 'lowPrice' in data:
                    high  = float(data['highPrice'])
                    low   = float(data['lowPrice'])
                    close = float(data['lastPrice'])

        if high and low and close:
            p  = (high + low + close) / 3
            r1 = (p * 2) - low
            s1 = (p * 2) - high
            r2 = p + (high - low)
            s2 = p - (high - low)
            decimals = 2 if close > 10 else 4
            return {
                'p':  round(p,  decimals),
                'r1': round(r1, decimals),
                's1': round(s1, decimals),
                'r2': round(r2, decimals),
                's2': round(s2, decimals)
            }
    except Exception as e:
        print(f"Error calculating pivots for {symbol}: {e}")

    return None
