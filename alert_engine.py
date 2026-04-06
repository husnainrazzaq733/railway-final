import json
import os
from db import alerts_collection

ALERTS_FILE = 'alerts.json'

def load_alerts():
    if alerts_collection is not None:
        return list(alerts_collection.find({}, {'_id': 0}))
    if not os.path.exists(ALERTS_FILE):
        return []
    try:
        with open(ALERTS_FILE, 'r') as f:
            return json.load(f)
    except Exception:
        return []

def save_alerts(alerts):
    if alerts_collection is not None:
        alerts_collection.delete_many({})
        if alerts:
            alerts_collection.insert_many(alerts)
        return
    with open(ALERTS_FILE, 'w') as f:
        json.dump(alerts, f)

def add_alert(chat_id, user_name, symbol, target_price, condition):
    # condition can be 'above' or 'below'
    alerts = load_alerts()
    # Find max id to avoid collisions
    max_id = max([a['id'] for a in alerts], default=0)
    alert_id = max_id + 1
    new_alert = {
        'id': alert_id,
        'chat_id': chat_id,
        'symbol': symbol,
        'target_price': target_price,
        'condition': condition,
        'user_name': user_name
    }
    alerts.append(new_alert)
    save_alerts(alerts)
    return alert_id

def remove_alert(alert_id):
    alerts = load_alerts()
    alerts = [a for a in alerts if a['id'] != alert_id]
    save_alerts(alerts)

def get_alerts(chat_id):
    alerts = load_alerts()
    return [a for a in alerts if a['chat_id'] == chat_id]
