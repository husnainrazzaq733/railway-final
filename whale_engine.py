import requests
import concurrent.futures
from rsi_api import get_top_usdt_coins

def get_whale_orders(symbol, market_type='swap', usd_threshold=1000000, multiplier=5):
    """
    Fetch order book depth and identify large 'whale' orders.
    """
    base_url = "https://fapi.binance.com/fapi/v1" if market_type == 'swap' else "https://api.binance.com/api/v3"
    url = f"{base_url}/depth?symbol={symbol}&limit=100"
    
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code != 200:
            return []
        data = resp.json()
        
        bids = data.get('bids', [])
        asks = data.get('asks', [])
        
        whales = []
        
        def analyze_side(side_data, side_name):
            if not side_data: return
            
            # volume in top 100
            volumes = [float(x[1]) for x in side_data]
            avg_vol = sum(volumes) / len(volumes) if volumes else 0
            
            for price_str, qty_str in side_data:
                price = float(price_str)
                qty = float(qty_str)
                usd_val = price * qty
                
                # A "Whale" is defined as:
                # 1. USD value > usd_threshold
                # 2. AND qty > multiplier * average volume of top levels
                if usd_val >= usd_threshold and qty >= (avg_vol * multiplier):
                    whales.append({
                        'symbol': symbol,
                        'side': side_name,
                        'price': price,
                        'qty': qty,
                        'usd_val': usd_val,
                        'multiple': qty / avg_vol if avg_vol > 0 else 0
                    })

        analyze_side(bids, 'BUY')
        analyze_side(asks, 'SELL')
        
        return whales
    except Exception as e:
        print(f"Error fetching whales for {symbol}: {e}")
        return []

def scan_whales(market_type='swap', limit=500, usd_threshold=1000000):
    """
    Scan top X coins for whale orders.
    """
    coins = get_top_usdt_coins(limit, market_type)
    results = []
    
    # Increased workers to 100 for very broad scanning
    with concurrent.futures.ThreadPoolExecutor(max_workers=100) as executor:
        futures = [executor.submit(get_whale_orders, coin, market_type, usd_threshold) for coin in coins]
        for future in concurrent.futures.as_completed(futures):
            whale_list = future.result()
            if whale_list:
                results.extend(whale_list)
                
    # Sort results by USD value descending
    results.sort(key=lambda x: x['usd_val'], reverse=True)
    return results
