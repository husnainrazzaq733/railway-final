import requests
import time
import json
import os
import concurrent.futures
from datetime import datetime

# Files to keep track of notified alerts
NOTIFIED_LIQ = "notified_liquidations.json"
NOTIFIED_FUNDING = "notified_funding.json"
LAST_VOLUMES = "last_volumes.json"

def fetch_all_tickers(market_type='swap'):
    url = "https://fapi.binance.com/fapi/v1/ticker/24hr" if market_type == 'swap' else "https://api.binance.com/api/v3/ticker/24hr"
    try:
        res = requests.get(url, timeout=10)
        if res.status_code == 200:
            return res.json()
    except:
        pass
    return []

def check_volume_spikes():
    """
    Detects sudden volume increases.
    Compares current 24h volume with the volume recorded 5-10 minutes ago.
    """
    tickers = fetch_all_tickers('swap')
    if not tickers: return []

    # Load last recorded volumes
    last_data = {}
    if os.path.exists(LAST_VOLUMES):
        try:
            with open(LAST_VOLUMES, 'r') as f:
                last_data = json.load(f)
        except: pass

    current_time = time.time()
    spikes = []
    new_last_data = {
        'timestamp': current_time,
        'volumes': {}
    }

    # Only process top 200 coins by volume to save resources
    tickers.sort(key=lambda x: float(x.get('quoteVolume', 0)), reverse=True)
    
    last_timestamp = last_data.get('timestamp', 0)
    time_diff = current_time - last_timestamp
    
    # We only check if at least 3 minutes have passed since last record
    check_spike = 180 < time_diff < 1200 # Between 3 and 20 mins

    for t in tickers[:200]:
        sym = t['symbol']
        curr_vol = float(t['quoteVolume'])
        new_last_data['volumes'][sym] = curr_vol

        if check_spike and sym in last_data.get('volumes', {}):
            prev_vol = last_data['volumes'][sym]
            increase = curr_vol - prev_vol
            
            # If volume increased by more than 2% of the ENTIRE 24h volume in just 5-10 mins
            # That's a massive spike. Or check for a specific USD amount.
            if increase > (prev_vol * 0.05) and increase > 500000: # 5% increase AND min $500k new vol
                spikes.append({
                    'symbol': sym,
                    'increase_pct': round((increase / prev_vol) * 100, 2),
                    'increase_usd': round(increase, 2),
                    'price': t['lastPrice']
                })

    # Save current volumes for next check
    with open(LAST_VOLUMES, 'w') as f:
        json.dump(new_last_data, f)
        
    return spikes

def check_funding_rates():
    """
    Checks for extreme funding rates in futures.
    """
    try:
        url = "https://fapi.binance.com/fapi/v1/premiumIndex"
        res = requests.get(url, timeout=10)
        if res.status_code == 200:
            data = res.json()
            extreme = []
            for item in data:
                rate = float(item.get('lastFundingRate', 0))
                abs_rate = abs(rate)
                
                # Threshold: > 0.03% (Normal is 0.01%)
                if abs_rate >= 0.0003: 
                    # Calculate Probability
                    if abs_rate < 0.0005:
                        prob = "60-70%"
                        risk = "Moderate"
                    elif abs_rate < 0.0008:
                        prob = "75-85%"
                        risk = "High"
                    else:
                        prob = "90-95%"
                        risk = "EXTREME"

                    extreme.append({
                        'symbol': item['symbol'],
                        'rate': round(rate * 100, 4),
                        'price': item['markPrice'],
                        'probability': prob,
                        'risk': risk
                    })
            return extreme
    except:
        pass
    return []

def check_liquidations():
    """
    Fetches recent large liquidations.
    """
    try:
        # Note: This endpoint returns recent liquidation orders across the market
        url = "https://fapi.binance.com/fapi/v1/allForceOrders?limit=50"
        res = requests.get(url, timeout=10)
        if res.status_code == 200:
            data = res.json()
            large_liqs = []
            
            # Load notified to avoid duplicates
            notified = []
            if os.path.exists(NOTIFIED_LIQ):
                try:
                    with open(NOTIFIED_LIQ, 'r') as f: notified = json.load(f)
                except: pass

            new_notified = list(notified)
            
            for liq in data:
                # We identify each liq by symbol + time + price
                liq_id = f"{liq['symbol']}_{liq['time']}_{liq['price']}"
                if liq_id in notified: continue
                
                price = float(liq['price'])
                qty = float(liq['origQty'])
                usd_val = price * qty
                
                # Only notify if > $50,000 liquidation
                if usd_val >= 50000:
                    large_liqs.append({
                        'symbol': liq['symbol'],
                        'side': liq['side'], # SELL means Long Liquidation, BUY means Short Liquidation
                        'usd_val': round(usd_val, 2),
                        'price': price
                    })
                    new_notified.append(liq_id)

            if large_liqs:
                if len(new_notified) > 200: new_notified = new_notified[-100:]
                with open(NOTIFIED_LIQ, 'w') as f: json.dump(new_notified, f)
                
            return large_liqs
    except Exception as e:
        print(f"Error checking liqs: {e}")
    return []

def get_symbol_liquidations(symbol):
    """
    Summarize recent liquidations for a specific symbol to find clusters.
    """
    try:
        # Fetch last 500 liquidations for this symbol
        url = f"https://fapi.binance.com/fapi/v1/allForceOrders?symbol={symbol}&limit=500"
        res = requests.get(url, timeout=10)
        if res.status_code == 200:
            data = res.json()
            if not data: return None
            
            long_liq_vol = 0
            short_liq_vol = 0
            clusters = {} # Price rounded to 0.5% or similar
            
            for liq in data:
                price = float(liq['price'])
                qty = float(liq['origQty'])
                usd_val = price * qty
                
                if liq['side'] == 'SELL':
                    long_liq_vol += usd_val
                else:
                    short_liq_vol += usd_val
                
                # Cluster prices (round to nearest significant level)
                # For high price coins, round to 10s, for low price round to 0.001s
                if price > 1000:
                    cluster_price = round(price / 10) * 10
                elif price > 10:
                    cluster_price = round(price, 1)
                else:
                    cluster_price = round(price, 3)
                    
                clusters[cluster_price] = clusters.get(cluster_price, 0) + usd_val

            # Find top 3 clusters
            sorted_clusters = sorted(clusters.items(), key=lambda x: x[1], reverse=True)
            
            return {
                'symbol': symbol,
                'long_vol': round(long_liq_vol, 2),
                'short_vol': round(short_liq_vol, 2),
                'top_clusters': sorted_clusters[:3]
            }
    except:
        pass
    return None
