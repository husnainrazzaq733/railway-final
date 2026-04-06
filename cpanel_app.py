import os
import asyncio
import threading
import requests
from flask import Flask, request, jsonify
from telegram import Update
from main import setup_bot

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

app = Flask(__name__)

# Initialize the Python Telegram Bot application
ptb_app = setup_bot()

# Global variable to store the asyncio loop running the background tasks
bot_loop = None

def run_bot_background():
    global bot_loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    bot_loop = loop
    
    if ptb_app:
        # Initialize and start the PTB internal managers (JobQueue, etc)
        loop.run_until_complete(ptb_app.initialize())
        loop.run_until_complete(ptb_app.start())
        print("Background PTB asyncio loop and JobQueue started.")
        
        # Keep the event loop running forever to handle callbacks
        loop.run_forever()

# Start the background thread for asyncio
thread = threading.Thread(target=run_bot_background, daemon=True)
thread.start()

# Automatically register webhook with Telegram
def set_telegram_webhook():
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    domain = os.environ.get("WEBHOOK_URL", "https://bot.nextgensmm.site")
    if token and domain:
        url = f"https://api.telegram.org/bot{token}/setWebhook"
        webhook_path = f"{domain.rstrip('/')}/telegram_webhook"
        try:
            r = requests.post(url, json={"url": webhook_path})
            print(f"Webhook setup response: {r.json()}")
        except Exception as e:
            print(f"Failed to set webhook: {e}")
    else:
        print("WARNING: WEBHOOK_URL environment variable is missing!")

# Run it
set_telegram_webhook()

@app.route('/')
def index():
    return "Bot is running perfectly on cPanel via Webhook!"

@app.route('/telegram_webhook', methods=['POST'])
def webhook():
    if not ptb_app or not bot_loop:
        return "Bot not fully initialized", 500
        
    try:
        json_data = request.get_json(force=True)
        update = Update.de_json(json_data, ptb_app.bot)
        
        # Schedule the update in the background PTB loop
        future = asyncio.run_coroutine_threadsafe(ptb_app.process_update(update), bot_loop)
        
        # WE MUST WAIT for the background thread to finish replying!
        # If we return instantly, cPanel freezes the app and the reply is never sent.
        try:
            future.result(timeout=15)
        except Exception as e:
            return jsonify({"status": "error", "message": f"Timeout or error: {e}"}), 500
            
        return jsonify({"status": "ok"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": f"Global Error: {e}"}), 500
