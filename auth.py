import json
import os
from db import auth_collection

AUTH_FILE = 'auth.json'

def _load_auth():
    if auth_collection is not None:
        doc = auth_collection.find_one({}, {'_id': 0})
        if doc: return doc
        return {"owner": None, "allowed_users": []}
    if not os.path.exists(AUTH_FILE):
        return {"owner": None, "allowed_users": []}
    try:
        with open(AUTH_FILE, 'r') as f:
            data = json.load(f)
            if "owner" not in data:
                data["owner"] = None
            if "allowed_users" not in data:
                data["allowed_users"] = []
            return data
    except Exception:
        return {"owner": None, "allowed_users": []}

def _save_auth(data):
    if auth_collection is not None:
        auth_collection.delete_many({})
        auth_collection.insert_one(data)
        return
    with open(AUTH_FILE, 'w') as f:
        json.dump(data, f)

def check_and_authorize(chat_id):
    """
    Checks if a user is authorized. 
    If there is no owner yet, makes this chat_id the owner!
    """
    data = _load_auth()
    
    # First user becomes the owner automatically
    if data["owner"] is None:
        data["owner"] = chat_id
        _save_auth(data)
        return True, True  # Authorized, is_new_owner
        
    is_owner = (data["owner"] == chat_id)
    is_allowed = (chat_id in data["allowed_users"])
    
    return is_owner or is_allowed, False

def add_user(chat_id):
    data = _load_auth()
    if chat_id not in data["allowed_users"] and data["owner"] != chat_id:
        data["allowed_users"].append(chat_id)
        _save_auth(data)
        return True
    return False

def remove_user(chat_id):
    data = _load_auth()
    if chat_id in data["allowed_users"]:
        data["allowed_users"].remove(chat_id)
        _save_auth(data)
        return True
    return False

def get_auth_data():
    return _load_auth()

def is_owner(chat_id):
    data = _load_auth()
    return data["owner"] == chat_id
