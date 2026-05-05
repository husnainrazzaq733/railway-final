import requests
import xml.etree.ElementTree as ET
import json
import os
from datetime import datetime

# Free RSS Feed from CryptoPanic (No API Key required)
RSS_URL = "https://cryptopanic.com/news/rss/"
NOTIFIED_FILE = "notified_social.json"

def fetch_rss_news():
    """
    Fetch latest market-moving news from CryptoPanic RSS feed.
    """
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        res = requests.get(RSS_URL, headers=headers, timeout=15)
        if res.status_code == 200:
            root = ET.fromstring(res.content)
            items = []
            for item in root.findall('./channel/item'):
                items.append({
                    'id': item.find('guid').text if item.find('guid') is not None else item.find('link').text,
                    'title': item.find('title').text,
                    'link': item.find('link').text,
                    'pubDate': item.find('pubDate').text
                })
            return items
    except Exception as e:
        print(f"Error fetching RSS social news: {e}")
    
    return []

def check_and_get_social_alerts():
    """
    Checks for new important news from RSS and returns those not yet notified.
    """
    posts = fetch_rss_news()
    if not posts:
        return []

    notified = []
    if os.path.exists(NOTIFIED_FILE):
        try:
            with open(NOTIFIED_FILE, "r") as f:
                notified = json.load(f)
        except:
            pass
            
    to_alert = []
    new_notified = list(notified)

    # We only take the top 5 newest from RSS to avoid spamming on restart
    for post in posts[:10]:
        pid = str(post['id'])
        if pid not in notified:
            to_alert.append({
                'id': pid,
                'title': post.get('title'),
                'url': post.get('link'),
                'source': 'Crypto Social/News',
                'currencies': [] # RSS doesn't give codes directly like API
            })
            new_notified.append(pid)
            
            if len(new_notified) > 200:
                new_notified = new_notified[-100:]
                 
    if to_alert:
         with open(NOTIFIED_FILE, "w") as f:
             json.dump(new_notified, f)
             
    return to_alert
