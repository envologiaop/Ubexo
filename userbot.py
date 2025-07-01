#!/usr/bin/env python3
import os
import asyncio
import logging
from datetime import datetime

# Import pyrogram components
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.errors import FloodWait

# Import shared application components
from app import app, db
from models import ChatHistory, UserContext
from gemini_client import GeminiClient
from utils import transcribe_voice, analyze_image, get_chat_context, format_error_message

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class UserbotManager:
    def __init__(self):
        self.client = None
        self.is_running = False
        self.gemini = GeminiClient()
        
    async def stop(self):
        """Gracefully stops the userbot client."""
        logger.info("Stopping userbot...")
        self.is_running = False
        if self.client and self.client.is_connected:
            await self.client.stop()
            logger.info("Userbot client stopped successfully.")
        
    async def initialize_client(self):
        """Initializes the Pyrogram client from the session string."""
        session_string = os.environ.get("TELEGRAM_SESSION_STRING")
        if not session_string:
            raise ValueError("TELEGRAM_SESSION_STRING environment variable is not set.")
            
        self.client = Client("envo_userbot", session_string=session_string)
        self.register_handlers()
        
    def register_handlers(self):
        """Registers all message handlers for the userbot commands."""
        
        @self.client.on_message(filters.me & filters.command("ask", prefixes="."))
        async def handle_ask_command(_, message: Message):
            await self.process_ask_command(message)

        # (Other command handlers like summarize, translate, etc., remain here)
        # ...

        @self.client.on_message(filters.me & filters.command("help", prefixes="."))
        async def handle_help_command(_, message: Message):
            await self.process_help_command(message)

        @self.client.on_message(~filters.me & ~filters.bot & filters.private)
        async def store_message(_, message: Message):
            # Only storing messages from private chats for context
            await self.store_chat_history(message)

    async def start(self):
        """Starts the userbot client and keeps it running."""
        try:
            logger.info("Initializing Telegram userbot...")
            await self.initialize_client()
            
            logger.info("Starting Telegram client...")
            await self.client.start()
            
            self.is_running = True
            me = await self.client.get_me()
            logger.info(f"✅ Envo userbot started successfully for {me.first_name} (@{me.username})")
            
            # Custom keep-alive loop. idle() can be unreliable in some environments.
            while self.is_running:
                if not self.client.is_connected:
                    logger.warning("Client disconnected. Userbot will shut down.")
                    self.is_running = False
                    break
                await asyncio.sleep(60) # Check connection status every minute
        
        except asyncio.CancelledError:
            logger.info("Userbot task was cancelled. Shutting down.")
        except Exception as e:
            logger.error(f"A critical error occurred in the userbot start sequence: {e}", exc_info=True)
        finally:
            self.is_running = False
            if self.client and self.client.is_initialized:
                logger.info("Ensuring userbot client is stopped.")
                await self.client.stop()
            logger.info("Userbot shutdown complete.")

    async def process_ask_command(self, message: Message):
        """Processes the .ask command with contextual AI response."""
        try:
            query = message.text.split(' ', 1)[1] if len(message.text.split(' ')) > 1 else None
            if not query:
                await message.edit_text("Usage: `.ask [your question]`")
                return
                
            await message.edit_text("🤔 Thinking...")
            
            context = await self.get_message_context(message)
            response = await self.gemini.generate_response(query, context, message.chat.id)
            
            await message.edit_text(response or "Sorry, I couldn't get a response.")
                
        except FloodWait as e:
            logger.warning(f"Flood wait of {e.value} seconds.")
            await asyncio.sleep(e.value)
            await message.edit_text(f"Telegram rate limit hit. Please wait {e.value}s.")
        except Exception as e:
            error_msg = format_error_message("AI Response", str(e))
            await message.edit_text(error_msg)
            logger.error(f"Ask command error: {e}", exc_info=True)

    # --- Other processing methods (process_content_command, etc.) ---
    # ... These methods can remain as they were, with robust error handling ...

    async def get_message_context(self, message: Message) -> str:
        # ... (implementation remains the same)
        return ""

    async def get_target_content(self, message: Message):
        # ... (implementation remains the same)
        return None
            
    async def store_chat_history(self, message: Message):
        """Stores a message in the database for future context."""
        if not message.text: # Don't store non-text messages for now
            return
        try:
            # Use app_context to safely interact with the database
            with app.app_context():
                chat_entry = ChatHistory(
                    chat_id=message.chat.id,
                    message_id=message.id,
                    user_id=message.from_user.id if message.from_user else 0,
                    first_name=message.from_user.first_name if message.from_user else "Unknown",
                    message_text=message.text,
                    timestamp=datetime.utcnow()
                )
                db.session.add(chat_entry)
                db.session.commit()
        except Exception as e:
            logger.error(f"Error storing chat history: {e}", exc_info=True)


# Note: The standalone start_userbot_background function is no longer needed
# as all control flows through the Flask app.
