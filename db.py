import os
import json
from pymongo import MongoClient

# Fetch the MONGO_URI from the environment variables (e.g. from Railway config)
MONGO_URI = os.environ.get("MONGO_URI")

client = None
db = None

alerts_collection = None
trades_collection = None
auth_collection = None

if MONGO_URI:
    try:
        client = MongoClient(MONGO_URI)
        db = client['trading_bot_db']
        
        alerts_collection = db['alerts']
        trades_collection = db['trades']
        auth_collection = db['auth']
        print("✅ MongoDB Connected Successfully!")
    except Exception as e:
        print(f"❌ MongoDB Connection failed: {e}")
        alerts_collection = None
        trades_collection = None
        auth_collection = None
else:
    print("⚠️ No MONGO_URI found. Falling back to local .json file storage.")
