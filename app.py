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
        
        # All credentials available - check userbot status
        global userbot_manager, userbot_thread
        
        if userbot_manager and hasattr(userbot_manager, 'is_running') and userbot_manager.is_running:
            return jsonify({
                "status": "running",
                "bot_name": "Envo AI Userbot", 
                "powered_by": "Envologia",
                "message": "Userbot is running! Commands are active in Telegram."
            })
        elif userbot_thread and userbot_thread.is_alive():
            return jsonify({
                "status": "starting",
                "bot_name": "Envo AI Userbot",
                "powered_by": "Envologia", 
                "message": "Userbot is starting up..."
            })
        else:
            return jsonify({
                "status": "ready",
                "bot_name": "Envo AI Userbot",
                "powered_by": "Envologia", 
                "message": "All credentials configured. Ready to start userbot."
            })
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)})

@app.route('/start_userbot', methods=['POST'])
def start_userbot_endpoint():
    """Start the userbot on demand"""
    try:
        global userbot_manager, userbot_thread
        
        # Check if userbot is already running
        if userbot_manager and hasattr(userbot_manager, 'is_running') and userbot_manager.is_running:
            return jsonify({"status": "already_running", "message": "Userbot is already active"})
        
        # Check if thread is already running
        if userbot_thread and userbot_thread.is_alive():
            return jsonify({"status": "already_running", "message": "Userbot thread is already active"})
        
        # Start userbot in a new thread with proper event loop handling
        def start_userbot_async():
            global userbot_manager
            try:
                import asyncio
                import sys
                
                # Import userbot outside of the async context to avoid sync module issues
                try:
                    from userbot import UserbotManager
                except ImportError as import_error:
                    logger.error(f"Failed to import UserbotManager: {import_error}")
                    return
                
                # Create and set new event loop for this thread
                if sys.version_info >= (3, 10):
                    try:
                        loop = asyncio.get_event_loop()
                    except RuntimeError:
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                else:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                
                try:
                    userbot_manager = UserbotManager()
                    
                    # Run the userbot with proper exception handling
                    loop.run_until_complete(userbot_manager.start())
                except Exception as e:
                    logger.error(f"Userbot execution error: {e}")
                    if userbot_manager:
                        userbot_manager.is_running = False
                finally:
                    # Properly clean up the event loop
                    try:
                        # Cancel all running tasks
                        pending = asyncio.all_tasks(loop)
                        for task in pending:
                            task.cancel()
                        
                        # Wait for tasks to be cancelled
                        if pending:
                            loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                    except Exception as cleanup_error:
                        logger.error(f"Error during cleanup: {cleanup_error}")
                    finally:
                        try:
                            loop.close()
                        except Exception:
                            pass
                
            except Exception as e:
                logger.error(f"Userbot thread error: {e}")
                # Ensure userbot_manager is marked as not running
                if userbot_manager:
                    userbot_manager.is_running = False
        
        # Start userbot thread
        userbot_thread = threading.Thread(target=start_userbot_async, daemon=True)
        userbot_thread.start()
        
        # Give it a moment to initialize
        time.sleep(2)
        
        return jsonify({
            "status": "started", 
            "message": "Userbot started successfully! You can now use commands in Telegram."
        })
            
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
