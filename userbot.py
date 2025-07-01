import os
import asyncio
import logging
from pyrogram import Client, filters
from pyrogram.types import Message
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

    async def initialize_client(self):
        """Initialize Pyrogram client"""
        session_string = os.environ.get("TELEGRAM_SESSION_STRING")
        if not session_string:
            raise ValueError("Missing TELEGRAM_SESSION_STRING in environment variables")
        self.client = Client("envo_userbot", session_string=session_string)
        self.register_handlers()

    def register_handlers(self):
        """Register message handlers"""
        # --- CHANGE 1: The command handler now listens for ".envo" ---
        @self.client.on_message(filters.me & filters.command("envo", prefixes="."))
        async def handle_ask_command(client, message: Message):
            await self.process_ask_command(message)

        @self.client.on_message(filters.me & filters.command("summarize", prefixes="."))
        async def handle_summarize_command(client, message: Message):
            await self.process_content_command(message, "summarize")

        @self.client.on_message(filters.me & filters.command("translate", prefixes="."))
        async def handle_translate_command(client, message: Message):
            await self.process_content_command(message, "translate")

        # ... (all other handlers remain the same) ...

        @self.client.on_message(filters.me & filters.command("help", prefixes="."))
        async def handle_help_command(client, message: Message):
            await self.process_help_command(message)

        @self.client.on_message(filters.me & filters.command("pass", prefixes="."))
        async def handle_pass_command(client, message: Message):
            await message.delete()

        @self.client.on_message(~filters.me & ~filters.bot)
        async def store_message(client, message: Message):
            await self.store_chat_history(message)

    async def start(self):
        """Start the userbot"""
        try:
            await self.initialize_client()
            await self.client.start()
            self.is_running = True
            logger.info("Envo userbot started successfully")
            await asyncio.Event().wait()
        except Exception as e:
            logger.error(f"Failed to start userbot: {e}")
            self.is_running = False

    async def process_ask_command(self, message: Message):
        """Process .envo command, prioritizing replied-to content."""
        try:
            # --- CHANGE 2: The question is extracted by removing ".envo" ---
            question = (message.text or "").replace(".envo", "").strip()

            # Get replied content first, as the primary subject
            replied_content = None
            if message.reply_to_message:
                reply_msg = message.reply_to_message
                if reply_msg.text:
                    replied_content = reply_msg.text
                elif reply_msg.photo:
                    try:
                        photo_path = await self.client.download_media(reply_msg.photo)
                        replied_content = f"Image content: {await analyze_image(photo_path)}"
                        os.remove(photo_path)
                    except Exception as e:
                        logger.error(f"Image analysis error: {e}")
                        replied_content = "Image: Could not analyze"
                elif reply_msg.voice:
                    try:
                        voice_path = await self.client.download_media(reply_msg.voice)
                        replied_content = f"Voice message transcription: {await transcribe_voice(voice_path)}"
                        os.remove(voice_path)
                    except Exception as e:
                        logger.error(f"Voice transcription error: {e}")
                        replied_content = "Voice: Could not transcribe"

            if not question and replied_content:
                question = "What do you think about this?"

            response = await self.gemini.generate_response(
                question=question,
                replied_content=replied_content,
                chat_id=message.chat.id
            )

            await self.client.send_message(message.chat.id, response)
            await message.delete()
        except Exception as e:
            error_msg = format_error_message("AI_ERROR", str(e))
            await self.client.send_message(message.chat.id, error_msg)
            await message.delete()
            logger.error(f"Error in envo command: {e}")
    
    # ... (process_content_command, process_analysis_command, etc. remain the same) ...

    async def process_help_command(self, message: Message):
        """Show help information as a new message."""
        # --- CHANGE 3: The help text now shows ".envo" ---
        help_text = """**Envo AI Userbot Commands:**

**AI & Questions:**
• `.envo [question]` - Ask the AI anything.
• `.pass` - Deletes your command message.

**Content Creation & Editing:**
(Reply to a message or add text after the command)
• `.summarize` - Summarize the text.
• `.translate` - Translate the text.
• `.rewrite` - Rewrite the text in a different style.
• `.improve` - Fix grammar and improve writing.
• `.expand` - Add more detail to the text.
• `.condense` - Make the text more concise.

**Analysis & Search:**
• `.analyze` - Analyze the content's key points.
• `.explain` - Explain a complex topic simply.
• `.search [query]` - Search your chat history for a keyword.

**Special Features:**
• `.roleplay [character]` - Start roleplaying as a character.
• `.clear` - Clears the current roleplay/context.
• `.help` - Shows this help message.

**Tips:**
- Reply to a message to provide context.
- The bot can see images and transcribe voice messages when you reply to them.

✨ *Powered by Envologia*"""
        
        try:
            await self.client.send_message(message.chat.id, help_text)
            await message.delete()
        except Exception as e:
            logger.error(f"Failed to send help message: {e}")
            await self.client.send_message(message.chat.id, "Sorry, couldn't fetch the help menu right now.")
            await message.delete()
            
    # ... (all other process methods and utility methods remain the same) ...

    async def get_target_content(self, message: Message):
        """Get content to process from command or reply"""
        command_parts = message.text.split(" ", 1)
        if len(command_parts) > 1 and command_parts[1].strip():
            return command_parts[1].strip()
        
        if message.reply_to_message and message.reply_to_message.text:
            return message.reply_to_message.text
        
        return None
    
    async def store_chat_history(self, message: Message):
        """Store message in chat history for context"""
        if message.text and message.text.startswith('.'):
            return
        try:
            with app.app_context():
                chat_history = ChatHistory(
                    chat_id=message.chat.id,
                    message_id=message.id,
                    user_id=message.from_user.id if message.from_user else None,
                    username=message.from_user.username if message.from_user else None,
                    first_name=message.from_user.first_name if message.from_user else None,
                    last_name=message.from_user.last_name if message.from_user else None,
                    message_text=message.text,
                    message_type='text' if message.text else 'other',
                    timestamp=datetime.utcnow()
                )
                db.session.add(chat_history)
                db.session.commit()
        except Exception as e:
            logger.error(f"Error storing chat history: {e}")
