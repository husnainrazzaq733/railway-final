import datetime
import json
import os

SESSION_STATE_FILE = "session_state.json"

# New York Time (UTC-4) Hours for Forex Sessions:
SESSIONS = {
    "Asia": {"start": 20, "end": 0, "emoji": "🇯🇵"},
    "London": {"start": 2, "end": 5, "emoji": "🇬🇧"},
    "New York": {"start": 7, "end": 10, "emoji": "🇺🇸"},
    "London Close": {"start": 10, "end": 12, "emoji": "🇬🇧"}
}

def get_ny_now():
    return datetime.datetime.utcnow() - datetime.timedelta(hours=4)

def is_session_active(session_name):
    now = get_ny_now()
    hour = now.hour
    
    session = SESSIONS[session_name]
    start = session['start']
    end = session['end']
    
    # If the session runs strictly within a single day
    if start < end:
        return start <= hour < end
    else:
        # If the session crosses midnight (e.g., Asia 20:00 to 00:00)
        return hour >= start or hour < end

def get_all_active_sessions():
    active = []
    for name in SESSIONS:
        if is_session_active(name):
            active.append(name)
    return active

def load_session_states():
    if not os.path.exists(SESSION_STATE_FILE):
        return {name: False for name in SESSIONS.keys()}
    try:
        with open(SESSION_STATE_FILE, 'r') as f:
            return json.load(f)
    except Exception:
        return {name: False for name in SESSIONS.keys()}

def save_session_states(states):
    with open(SESSION_STATE_FILE, 'w') as f:
        json.dump(states, f)

def check_for_state_changes():
    """
    Checks if any session transitioned from closed->open or open->closed.
    Returns a list of messages to broadcast.
    """
    old_states = load_session_states()
    new_states = {name: is_session_active(name) for name in SESSIONS}
    
    messages_to_send = []
    has_changes = False
    
    # Do not alert on weekend closures/opens typically, but let's check day of week
    now = get_ny_now()
    # Let's say we still alert, but Forex is closed on weekends.
    # We will just do strictly time-based alerts.
    
    for name in SESSIONS:
        was_active = old_states.get(name, False)
        is_active = new_states[name]
        emoji = SESSIONS[name]['emoji']
        
        if is_active and not was_active:
            # Session Started
            msg = f"{emoji} **{name} Session is now OPEN!**"
            messages_to_send.append(msg)
            has_changes = True
            
        elif not is_active and was_active:
            # Session Ended
            msg = f"🛑 **{name} Session has CLOSED.**"
            messages_to_send.append(msg)
            has_changes = True
            
    if has_changes:
        save_session_states(new_states)
        
    return messages_to_send
