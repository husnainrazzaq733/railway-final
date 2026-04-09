import requests
import datetime
import json
import os

NOTIFIED_FILE = "notified_news.json"

def fetch_ff_calendar():
    url = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code == 200:
            return res.json()
    except Exception as e:
        print(f"Error fetching news: {e}")
    return []

def get_upcoming_high_impact_news(minutes_ahead=30):
    events = fetch_ff_calendar()
    if not events:
        return []

    # Get current time in UTC
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    upcoming = []

    for event in events:
        if event.get('impact') == 'High' and event.get('country') == 'USD':
            date_str = event.get('date', "")
            if not date_str:
                continue
            
            try:
                # Python 3.7+ fromisoformat handles standard offset formats
                if date_str.endswith("Z"):
                    date_str = date_str[:-1] + "+00:00"
                
                event_time_utc = datetime.datetime.fromisoformat(date_str).astimezone(datetime.timezone.utc)
                delta_minutes = (event_time_utc - now_utc).total_seconds() / 60.0
                
                # Check if it occurs exactly within the next tracking window
                if 0 < delta_minutes <= minutes_ahead:
                    upcoming.append({
                        'title': event.get('title'),
                        'time_left': int(delta_minutes),
                        'event_time_utc': event_time_utc,
                        'forecast': event.get('forecast', 'N/A'),
                        'previous': event.get('previous', 'N/A'),
                        # fallback ID if no native ID from FF
                        'id': event.get('id', event.get('title') + "_" + date_str) 
                    })
            except Exception as e:
                pass

    return upcoming

def check_and_get_news_alerts():
    # Look ahead 30 mins to allow the 15min and 20min job loops to catch it reliably
    upcoming = get_upcoming_high_impact_news(30) 
    
    notified = []
    if os.path.exists(NOTIFIED_FILE):
        try:
            with open(NOTIFIED_FILE, "r") as f:
                notified = json.load(f)
        except:
            pass
            
    to_alert = []
    new_notified = list(notified)

    for item in upcoming:
        uid = str(item['id'])
        if uid not in notified:
            to_alert.append(item)
            new_notified.append(uid)
            # keep array bounded
            if len(new_notified) > 100:
                 new_notified = new_notified[-50:]
                 
    if to_alert:
         with open(NOTIFIED_FILE, "w") as f:
             json.dump(new_notified, f)
             
    return to_alert

def get_today_high_impact_news():
    """آج کی تمام High Impact USD news return کرتی ہے (پرانی اور آنے والی دونوں)۔"""
    events = fetch_ff_calendar()
    if not events:
        return []

    now_utc = datetime.datetime.now(datetime.timezone.utc)
    # PKT = UTC+5
    today_pkt = (now_utc + datetime.timedelta(hours=5)).date()

    todays_events = []
    for event in events:
        if event.get('impact') == 'High' and event.get('country') == 'USD':
            date_str = event.get('date', "")
            if not date_str:
                continue
            try:
                if date_str.endswith("Z"):
                    date_str = date_str[:-1] + "+00:00"
                event_time_utc = datetime.datetime.fromisoformat(date_str).astimezone(datetime.timezone.utc)
                event_time_pkt = event_time_utc + datetime.timedelta(hours=5)
                if event_time_pkt.date() == today_pkt:
                    delta_minutes = (event_time_utc - now_utc).total_seconds() / 60.0
                    status = "✅ Done" if delta_minutes < 0 else f"⏳ in ~{int(delta_minutes)} mins"
                    todays_events.append({
                        'title': event.get('title'),
                        'event_time_pkt': event_time_pkt,
                        'forecast': event.get('forecast', 'N/A'),
                        'previous': event.get('previous', 'N/A'),
                        'status': status,
                        'is_past': delta_minutes < 0
                    })
            except Exception:
                pass

    # time کے حساب سے sort کریں
    todays_events.sort(key=lambda x: x['event_time_pkt'])
    return todays_events
