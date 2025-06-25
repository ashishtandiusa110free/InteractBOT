from flask import Flask, jsonify
import threading
import time
import os
import logging
from datetime import datetime

# Create Flask app for keep-alive functionality
app = Flask(__name__)

# Configure Flask logging to match bot logging
app.logger.setLevel(logging.INFO)

# Global variables to track bot status
bot_status = {
    'started_at': None,
    'last_update': None,
    'total_users': 0,
    'total_messages': 0,
    'status': 'starting'
}

@app.route('/')
def home():
    """Health check endpoint with detailed status"""
    return jsonify({
        'status': 'alive',
        'message': 'Telegram Bot Keep-Alive Server',
        'timestamp': datetime.now().isoformat(),
        'uptime_seconds': int(time.time() - bot_status['started_at']) if bot_status['started_at'] else 0,
        'bot_status': bot_status['status']
    })

@app.route('/health')
def health():
    """Detailed health check endpoint"""
    uptime = int(time.time() - bot_status['started_at']) if bot_status['started_at'] else 0
    return jsonify({
        'status': 'healthy',
        'bot_status': bot_status['status'],
        'uptime_seconds': uptime,
        'uptime_human': f"{uptime // 3600}h {(uptime % 3600) // 60}m {uptime % 60}s",
        'started_at': bot_status['started_at'],
        'last_update': bot_status['last_update'],
        'total_users': bot_status['total_users'],
        'total_messages': bot_status['total_messages'],
        'environment': 'production' if os.getenv('REPL_ID') else 'development'
    })

@app.route('/status')
def status():
    """Simple status endpoint for monitoring"""
    return {
        'alive': True,
        'status': bot_status['status'],
        'uptime': int(time.time() - bot_status['started_at']) if bot_status['started_at'] else 0
    }

@app.route('/ping')
def ping():
    """Simple ping endpoint"""
    return 'pong'

def update_bot_status(status=None, users=None, messages=None):
    """Update bot status information"""
    global bot_status
    
    if status:
        bot_status['status'] = status
    if users is not None:
        bot_status['total_users'] = users
    if messages is not None:
        bot_status['total_messages'] = messages
    
    bot_status['last_update'] = time.time()

def run():
    """Run the Flask server with enhanced configuration"""
    try:
        # Disable Flask request logging in production to reduce noise
        if os.getenv('REPL_ID'):
            logging.getLogger('werkzeug').setLevel(logging.WARNING)
        
        # Try different ports if 8080 is occupied
        ports_to_try = [8080, 8081, 8082, 8083, 8084]
        server_started = False
        
        for port in ports_to_try:
            try:
                app.run(
                    host='0.0.0.0', 
                    port=port, 
                    debug=False,
                    threaded=True,  # Enable threading for better performance
                    use_reloader=False  # Disable reloader to prevent conflicts
                )
                server_started = True
                break
            except OSError as port_error:
                if "Address already in use" in str(port_error):
                    print(f"Port {port} in use, trying next port...")
                    continue
                else:
                    raise port_error
        
        if not server_started:
            print("Could not start keep-alive server on any available port")
            
    except Exception as e:
        print(f"Keep-alive server error: {e}")

def keep_alive():
    """Start the Flask server in a separate daemon thread for 24/7 operation"""
    global bot_status
    
    # Initialize bot status
    bot_status['started_at'] = time.time()
    bot_status['status'] = 'initializing'
    
    # Create and start the keep-alive thread
    server_thread = threading.Thread(target=run, name='KeepAliveServer')
    server_thread.daemon = True  # Daemon thread dies when main thread dies
    server_thread.start()
    
    print("🚀 Keep-alive server started on port 8080")
    print("📊 Health check available at: http://localhost:8080/health")
    print("🔍 Status endpoint: http://localhost:8080/status")
    
    # Small delay to ensure server starts
    time.sleep(0.5)
    
    return server_thread

def heartbeat():
    """Send periodic heartbeat to update last_update timestamp"""
    def _heartbeat():
        while True:
            try:
                bot_status['last_update'] = time.time()
                # Send heartbeat every 30 seconds
                time.sleep(30)
            except Exception as e:
                print(f"Heartbeat error: {e}")
                time.sleep(30)
    
    heartbeat_thread = threading.Thread(target=_heartbeat, name='Heartbeat')
    heartbeat_thread.daemon = True
    heartbeat_thread.start()
    
    return heartbeat_thread

def set_bot_ready():
    """Mark bot as ready and running"""
    update_bot_status('running')
