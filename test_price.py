import sys
sys.path.append('c:/Users/HP/Desktop/arpyro alrat')
from price_api import get_price

print('Testing Crypto:')
crypto_price, c_domain, c_symbol = get_price('BTCUSDT')
print(f"BTCUSDT -> {c_symbol}: {crypto_price} (domain: {c_domain})")

print('\nTesting Forex:')
forex_price, f_domain, f_symbol = get_price('EURUSD=X')
print(f"EURUSD=X -> {f_symbol}: {forex_price} (domain: {f_domain})")
