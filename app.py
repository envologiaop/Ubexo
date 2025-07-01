import os
import logging
import threading
import time
from flask import Flask, render_template, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from werkzeug.middleware.proxy_fix import ProxyFix

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)

# Create the Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "envo-userbot-secret-key")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# Configure the database
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "postgresql://localhost/envo_userbot")
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}

# Initialize the app with the extension
db.init_app(app)

# Global variable to track userbot status
userbot_manager = None
userbot_thread = None

@app.route('/')
def index():
    """Main dashboard showing userbot status"""
    return render_template('dashboard.html')

@app.route('/health')
def health():
    """Health check endpoint for Render"""
    return jsonify({"status": "healthy", "service": "Envo Telegram Userbot"})

@app.route('/status')
def status():
    """Get userbot status"""
    try:
        # Check if we have required credentials
        session_string = os.environ.get("TELEGRAM_SESSION_STRING")
        gemini_key = os.environ.get("GEMINI_API_KEY")
        
        if not session_string:
            return jsonify({
                "status": "missing_credentials",
                "error": "Telegram session string not configured",
                "bot_name": "Envo AI Userbot",
                "powered_by": "Envologia"
            })
        
        if not gemini_key:
            return jsonify({
                "status": "missing_credentials", 
                "error": "Gemini API key not configured",
                "bot_name": "Envo AI Userbot",
                "powered_by": "Envologia"
            })
        
        # All credentials available - userbot can be started
        global userbot_manager
        if userbot_manager and hasattr(userbot_manager, 'is_running'):
            return jsonify({
                "status": "running" if userbot_manager.is_running else "ready",
                "bot_name": "Envo AI Userbot", 
                "powered_by": "Envologia",
                "message": "All credentials configured. Userbot ready to start."
            })
        else:
            return jsonify({
                "status": "ready",
                "bot_name": "Envo AI Userbot",
                "powered_by": "Envologia", 
                "message": "All credentials configured. Use standalone userbot service to start."
            })
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)})

@app.route('/start_userbot', methods=['POST'])
def start_userbot_endpoint():
    """Start the userbot on demand"""
    try:
        import subprocess
        import sys
        
        # Check if userbot process is already running
        try:
            result = subprocess.run(['pgrep', '-f', 'userbot_service'], capture_output=True, text=True)
            if result.returncode == 0 and result.stdout.strip():
                return jsonify({"status": "already_running", "message": "Userbot is already active"})
        except:
            pass
        
        # Start userbot service in background
        try:
            # Use current working directory for deployment compatibility
            current_dir = os.path.dirname(os.path.abspath(__file__))
            process = subprocess.Popen([
                sys.executable, 'userbot_service.py'
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, 
               cwd=current_dir, 
               preexec_fn=os.setsid if hasattr(os, 'setsid') else None)
            
            return jsonify({
                "status": "started", 
                "message": "Userbot started successfully! You can now use commands in Telegram.",
                "pid": process.pid
            })
        except Exception as e:
            return jsonify({"status": "error", "error": f"Failed to start userbot process: {str(e)}"})
            
    except Exception as e:
        logger.error(f"Failed to start userbot via endpoint: {e}")
        return jsonify({"status": "error", "error": str(e)})

def start_userbot_background():
    """Initialize userbot manager without starting it"""
    global userbot_manager
    
    # Check if we have the required Telegram session string
    session_string = os.environ.get("TELEGRAM_SESSION_STRING")
    if not session_string:
        logger.info("TELEGRAM_SESSION_STRING not found - userbot features will be limited")
        return
    
    try:
        from userbot import UserbotManager
        userbot_manager = UserbotManager()
        logger.info("Userbot manager initialized successfully")
        
        # Note: Actual userbot start will be handled separately or on-demand
        # This prevents event loop conflicts in the web service
        
    except Exception as e:
        logger.error(f"Failed to initialize userbot manager: {e}")

# Initialize database when app context is available
def initialize_app():
    """Initialize the application"""
    with app.app_context():
        # Import models here so tables are created
        import models
        db.create_all()
        logger.info("Database tables created successfully")
        
        # Initialize userbot manager if session string is available
        session_string = os.environ.get("TELEGRAM_SESSION_STRING")
        if session_string:
            logger.info("Telegram session string found - userbot features available")
        else:
            logger.info("No Telegram session string - userbot features disabled")

# Call initialization after a short delay to ensure everything is ready
def delayed_init():
    time.sleep(3)  # Wait 3 seconds for app to be fully ready
    initialize_app()

# Start initialization in a separate thread
init_thread = threading.Thread(target=delayed_init, daemon=True)
init_thread.start()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
