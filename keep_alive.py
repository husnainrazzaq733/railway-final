from flask import Flask
from threading import Thread
import logging

# Disable flask logging to keep console clean
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

app = Flask('')

@app.route('/')
def home():
    return "Bot is alive!"

def run():
    app.run(host='0.0.0.0', port=7860)

def keep_alive():
    t = Thread(target=run)
    t.start()
