import yfinance as yf
import requests

symbols = ['XAUUSD=X', 'GC=F', 'GOLD']
for s in symbols:
    try:
        t = yf.Ticker(s)
        print(f"yfinance {s}: {t.fast_info.last_price}", flush=True)
    except Exception as e:
         print(f"yfinance {s}: {e}", flush=True)

try:
    url = f"https://api.binance.com/api/v3/ticker/price?symbol=PAXGUSDT"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        print(f"Binance PAXGUSDT: {data.get('price')}", flush=True)
except Exception as e:
    print(f"Binance PAXGUSDT error: {e}", flush=True)
