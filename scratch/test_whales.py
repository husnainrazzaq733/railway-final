import requests

def get_whales(symbol, market_type='swap'):
    base_url = "https://fapi.binance.com/fapi/v1" if market_type == 'swap' else "https://api.binance.com/api/v3"
    url = f"{base_url}/depth?symbol={symbol}&limit=100"
    
    try:
        resp = requests.get(url, timeout=10)
        data = resp.json()
        
        bids = data.get('bids', [])
        asks = data.get('asks', [])
        
        whales = []
        
        # Helper to analyze side
        def analyze_side(side_data, side_name):
            if not side_data: return
            
            # total volume in top 100
            volumes = [float(x[1]) for x in side_data]
            avg_vol = sum(volumes) / len(volumes)
            
            for price_str, qty_str in side_data:
                price = float(price_str)
                qty = float(qty_str)
                usd_val = price * qty
                
                # Criteria: 
                # 1. USD value > $500,000 (Adjustable)
                # 2. OR qty > 10x average of top 100
                if usd_val > 500000 or qty > (avg_vol * 10):
                    whales.append({
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
        print(f"Error: {e}")
        return []

# Test with BTC
print("BTC Whales (Swap):")
whales = get_whales("BTCUSDT", 'swap')
for w in whales:
    print(f"{w['side']} | Price: {w['price']} | Qty: {w['qty']} | USD: ${w['usd_val']:,.0f} | {w['multiple']:.1f}x avg")

# Test with a smaller coin like SOL
print("\nSOL Whales (Swap):")
whales = get_whales("SOLUSDT", 'swap')
for w in whales:
    print(f"{w['side']} | Price: {w['price']} | Qty: {w['qty']} | USD: ${w['usd_val']:,.0f} | {w['multiple']:.1f}x avg")
