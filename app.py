#!/usr/bin/env python3
import os
import logging
import threading
import time
import asyncio
import sys
from flask import Flask, render_template, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from werkzeug.middleware.proxy_fix import ProxyFix

# --- Basic Setup ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# --- Database Initialization ---
class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)

# --- Flask App Initialization ---
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "envo-userbot-secret-key-dev")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# --- Database Configuration ---
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "postgresql://user:password@localhost/envo_userbot")
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 280, # Shorter than Render's default idle timeout
    "pool_pre_ping": True,
}

# Initialize SQLAlchemy with the app
db.init_app(app)

# --- Global State Management ---
# Using a dictionary to hold state is a bit cleaner for managing the userbot
userbot_state = {
    "thread": None,
    "manager": None,
}


# --- Web Routes ---
@app.route('/')
def index():
    """Renders the main dashboard UI."""
    return render_template('dashboard.html')

@app.route('/health')
def health():
    """A simple health check endpoint for Render to confirm the service is up."""
    return jsonify({"status": "healthy", "service": "Envo Web Service"})

@app.route('/status')
def status():
    """Provides the current status of the userbot."""
    bot_name = "Envo AI Userbot"
    powered_by = "Envologia"

    session_string = os.environ.get("TELEGRAM_SESSION_STRING")
    gemini_key = os.environ.get("GEMINI_API_KEY")

    if not session_string or not gemini_key:
        error_msg = "Telegram session string" if not session_string else "Gemini API key"
        return jsonify({
            "status": "missing_credentials",
            "error": f"{error_msg} is not configured.",
            "bot_name": bot_name,
            "powered_by": powered_by
        })

    manager = userbot_state.get("manager")
    thread = userbot_state.get("thread")

    if manager and hasattr(manager, 'is_running') and manager.is_running:
        return jsonify({
            "status": "running",
            "bot_name": bot_name,
            "powered_by": powered_by,
            "message": "Userbot is running! Commands are active in Telegram."
        })
    elif thread and thread.is_alive():
        return jsonify({
            "status": "starting",
            "bot_name": bot_name,
            "powered_by": powered_by,
            "message": "Userbot is starting up..."
        })
    else:
        return jsonify({
            "status": "ready",
            "bot_name": bot_name,
            "powered_by": powered_by,
            "message": "All credentials are configured. Ready to start the userbot."
        })

@app.route('/start_userbot', methods=['POST'])
def start_userbot_endpoint():
    """Endpoint to start the userbot in a background thread."""
    thread = userbot_state.get("thread")

    if thread and thread.is_alive():
        return jsonify({"status": "already_running", "message": "Userbot is already starting or running."})

    def start_userbot_in_thread():
        """
        Target function for the background thread.
        It creates and manages its own asyncio event loop.
        """
        # 1. Create and set a new event loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        logger.info("New event loop created for the userbot thread.")

        try:
            from userbot import UserbotManager
            
            # 2. Initialize the manager and store it in the global state
            manager = UserbotManager()
            userbot_state["manager"] = manager
            
            # 3. Run the userbot's main async start function
            logger.info("Starting UserbotManager...")
            loop.run_until_complete(manager.start())

        except Exception as e:
            logger.error(f"Userbot thread encountered a critical error: {e}", exc_info=True)
            if userbot_state.get("manager"):
                userbot_state["manager"].is_running = False
        finally:
            logger.info("Userbot thread has finished execution. Closing its event loop.")
            loop.close()

    try:
        # 4. Create and start the daemon thread
        new_thread = threading.Thread(target=start_userbot_in_thread, daemon=True)
        new_thread.start()
        userbot_state["thread"] = new_thread
        
        logger.info("Userbot start process initiated in a background thread.")
        time.sleep(2) # Give a moment for the thread to initialize
        
        return jsonify({
            "status": "started", 
            "message": "Userbot start command issued. Check status for updates."
        })
            
    except Exception as e:
        logger.error(f"Failed to start userbot thread from endpoint: {e}", exc_info=True)
        return jsonify({"status": "error", "error": f"Failed to create userbot thread: {e}"})

# --- Application Initialization Logic ---
def initialize_database():
    """
    Creates all database tables defined in the models.
    This should be called within the app context.
    """
    with app.app_context():
        logger.info("Initializing database and creating tables...")
        try:
            # Import models here to ensure they are registered with SQLAlchemy
            import models
            db.create_all()
            logger.info("Database tables checked/created successfully.")
        except Exception as e:
            logger.error(f"Error during database initialization: {e}", exc_info=True)

# Run the database initialization when the application starts
initialize_database()

if __name__ == '__main__':
    # Use the PORT environment variable provided by Render
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
