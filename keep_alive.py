from flask import Flask
import threading

app = Flask('')

@app.route('/')
def home():
    return "I'm alive!"  # Responds to pings from Railway to keep the bot alive

def run():
    app.run(host='0.0.0.0', port=8080)  # Flask listens on port 8080

def keep_alive():
    t = threading.Thread(target=run)
    t.start()  # Start Flask in a separate thread so it doesn't block your bot
