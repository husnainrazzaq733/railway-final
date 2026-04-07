import json
import os
from db import trades_collection

TRADES_FILE = 'trades.json'

def load_trades():
    if trades_collection is not None:
        return list(trades_collection.find({}, {'_id': 0}))
    if not os.path.exists(TRADES_FILE):
        return []
    try:
        with open(TRADES_FILE, 'r') as f:
            return json.load(f)
    except Exception:
        return []

def save_trades(trades):
    if trades_collection is not None:
        trades_collection.delete_many({})
        if trades:
            trades_collection.insert_many(trades)
        return
    with open(TRADES_FILE, 'w') as f:
        json.dump(trades, f)

def add_trade(chat_id, user_name, symbol, entry_price, stop_loss):
    trades = load_trades()
    max_id = max([t['id'] for t in trades], default=0)
    trade_id = max_id + 1
    
    is_long = entry_price > stop_loss
    risk = abs(entry_price - stop_loss)
    
    if is_long:
        t1 = entry_price + (risk * 1.5)
        t2 = entry_price + (risk * 2.0)
        t3 = entry_price + (risk * 3.0)
    else:
        t1 = entry_price - (risk * 1.5)
        t2 = entry_price - (risk * 2.0)
        t3 = entry_price - (risk * 3.0)
        
    new_trade = {
        'id': trade_id,
        'chat_id': chat_id,
        'user_name': user_name,
        'symbol': symbol,
        'entry_price': entry_price,
        'stop_loss': stop_loss,
        'is_long': is_long,
        'risk': risk,
        't1': t1,
        't2': t2,
        't3': t3,
        't1_hit': False,
        't2_hit': False
    }
    
    trades.append(new_trade)
    save_trades(trades)
    return trade_id, new_trade

def remove_trade(trade_id):
    trades = load_trades()
    trades = [t for t in trades if t['id'] != trade_id]
    save_trades(trades)

def get_user_trades(chat_id):
    trades = load_trades()
    return [t for t in trades if t['chat_id'] == chat_id]

def update_trade_target_hit(trade_id, target_level):
    trades = load_trades()
    for t in trades:
        if t['id'] == trade_id:
            if target_level == 1:
                t['t1_hit'] = True
            elif target_level == 2:
                t['t1_hit'] = True
                t['t2_hit'] = True
            break
    save_trades(trades)

def update_trade_sl(trade_id, new_sl):
    trades = load_trades()
    for t in trades:
        if t['id'] == trade_id:
            t['stop_loss'] = new_sl
            break
    save_trades(trades)
