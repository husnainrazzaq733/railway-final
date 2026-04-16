import json
import os
from db import trades_collection, history_collection

TRADES_FILE = 'trades.json'
HISTORY_FILE = 'history.json'

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

def add_trade(chat_id, user_name, symbol, entry_price, stop_loss, status='active', limit_condition=None):
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
        't2_hit': False,
        't3_hit': False,
        'status': status,
        'limit_condition': limit_condition
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
            elif target_level == 3:
                t['t1_hit'] = True
                t['t2_hit'] = True
                t['t3_hit'] = True
            break
    save_trades(trades)

def update_trade_sl(trade_id, new_sl):
    trades = load_trades()
    for t in trades:
        if t['id'] == trade_id:
            t['stop_loss'] = new_sl
            break
    save_trades(trades)

def update_trade_status(trade_id, status):
    trades = load_trades()
    for t in trades:
        if t['id'] == trade_id:
            t['status'] = status
            break
    save_trades(trades)

def mark_trade_history_logged(trade_id):
    trades = load_trades()
    for t in trades:
        if t['id'] == trade_id:
            t['history_logged'] = True
            break
    save_trades(trades)

def load_history():
    if history_collection is not None:
        return list(history_collection.find({}, {'_id': 0}))
    if not os.path.exists(HISTORY_FILE):
        return []
    try:
        with open(HISTORY_FILE, 'r') as f:
            return json.load(f)
    except Exception:
        return []

def save_history(history):
    if history_collection is not None:
        history_collection.delete_many({})
        if history:
            history_collection.insert_many(history)
        return
    with open(HISTORY_FILE, 'w') as f:
        json.dump(history, f)

def add_history_record(chat_id, symbol, is_long, result_pips, outcome, pnl_raw=0):
    import datetime
    history = load_history()
    record = {
        'chat_id': chat_id,
        'symbol': symbol,
        'is_long': is_long,
        'result_pips': result_pips,
        'outcome': outcome,
        'pnl_raw': pnl_raw,
        'date': datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    }
    history.append(record)
    save_history(history)
    return record

def get_user_stats(chat_id):
    history = load_history()
    user_hist = [h for h in history if h['chat_id'] == chat_id]
    
    total = len(user_hist)
    won = sum(1 for h in user_hist if h['outcome'] == 'Win')
    lost = sum(1 for h in user_hist if h['outcome'] == 'Loss')
    breakeven = sum(1 for h in user_hist if h['outcome'] == 'Breakeven')
    total_pips = sum(h.get('result_pips', 0) for h in user_hist)
    
    win_rate = 0
    if (won + lost) > 0:
        win_rate = (won / (won + lost)) * 100
        
    return {
        'total': total,
        'won': won,
        'lost': lost,
        'breakeven': breakeven,
        'total_pips': total_pips,
        'win_rate': round(win_rate, 2),
        'history': user_hist[-10:]
    }
