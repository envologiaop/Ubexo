import os
import asyncio
import logging
import threading
import time
from datetime import datetime, timedelta
from pyrogram import Client
from pyrogram import filters
from pyrogram.types import Message
from app import app, db
from models import ChatHistory, UserContext, CommandQueue
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
            
        self.client = Client(
            "envo_userbot",
            session_string=session_string
        )
        
        # Register handlers
        self.register_handlers()
        
    def register_handlers(self):
        """Register message handlers"""
        
        @self.client.on_message(filters.me & filters.command("ask", prefixes="."))
        async def handle_ask_command(client, message: Message):
            await self.process_ask_command(message)
            
        @self.client.on_message(filters.me & filters.command("summarize", prefixes="."))
        async def handle_summarize_command(client, message: Message):
            await self.process_content_command(message, "summarize")
            
        @self.client.on_message(filters.me & filters.command("translate", prefixes="."))
        async def handle_translate_command(client, message: Message):
            await self.process_content_command(message, "translate")
            
        @self.client.on_message(filters.me & filters.command("rewrite", prefixes="."))
        async def handle_rewrite_command(client, message: Message):
            await self.process_content_command(message, "rewrite")
            
        @self.client.on_message(filters.me & filters.command("improve", prefixes="."))
        async def handle_improve_command(client, message: Message):
            await self.process_content_command(message, "improve")
            
        @self.client.on_message(filters.me & filters.command("expand", prefixes="."))
        async def handle_expand_command(client, message: Message):
            await self.process_content_command(message, "expand")
            
        @self.client.on_message(filters.me & filters.command("condense", prefixes="."))
        async def handle_condense_command(client, message: Message):
            await self.process_content_command(message, "condense")
            
        @self.client.on_message(filters.me & filters.command("analyze", prefixes="."))
        async def handle_analyze_command(client, message: Message):
            await self.process_analysis_command(message, "analyze")
            
        @self.client.on_message(filters.me & filters.command("explain", prefixes="."))
        async def handle_explain_command(client, message: Message):
            await self.process_analysis_command(message, "explain")
            
        @self.client.on_message(filters.me & filters.command("search", prefixes="."))
        async def handle_search_command(client, message: Message):
            await self.process_search_command(message)
            
        @self.client.on_message(filters.me & filters.command("roleplay", prefixes="."))
        async def handle_roleplay_command(client, message: Message):
            await self.process_roleplay_command(message)
            
        @self.client.on_message(filters.me & filters.command("clear", prefixes="."))
        async def handle_clear_command(client, message: Message):
            await self.process_clear_command(message)
            
        @self.client.on_message(filters.me & filters.command("help", prefixes="."))
        async def handle_help_command(client, message: Message):
            await self.process_help_command(message)
            
        @self.client.on_message(filters.me & filters.command("pass", prefixes="."))
        async def handle_pass_command(client, message: Message):
            # Just delete the command message
            await message.delete()
        
        # Store all messages for context
        @self.client.on_message()
        async def store_message(client, message: Message):
            await self.store_chat_history(message)
    
    async def start(self):
        """Start the userbot"""
        try:
            await self.initialize_client()
            await self.client.start()
            self.is_running = True
            logger.info("Envo userbot started successfully")
            
            # Keep the client running
            await asyncio.Event().wait()
            
        except Exception as e:
            logger.error(f"Failed to start userbot: {e}")
            self.is_running = False
    
    async def process_ask_command(self, message: Message):
        """Process .ask command with AI response"""
        try:
            # Show thinking message
            thinking_msg = await message.edit_text("thinking...")
            await asyncio.sleep(1)
            
            # Extract question from command
            command_text = message.text or ""
            question = command_text.replace(".ask", "").strip()
            
            # Get context from replied message or recent chat
            context = await self.get_message_context(message)
            
            # Generate response
            response = await self.gemini.generate_response(question, context, message.chat.id)
            
            # Edit message with response (clean, natural format)
            await thinking_msg.edit_text(response)
            
        except Exception as e:
            error_msg = format_error_message("AI_ERROR", str(e))
            await message.edit_text(error_msg)
            logger.error(f"Error in ask command: {e}")
    
    async def process_content_command(self, message: Message, command_type: str):
        """Process content creation commands"""
        try:
            thinking_msg = await message.edit_text("working on it...")
            await asyncio.sleep(1)
            
            # Get target content
            target_content = await self.get_target_content(message)
            if not target_content:
                await thinking_msg.edit_text("need something to work with - reply to a message or include some text")
                return
            
            # Generate response based on command type
            response = await self.gemini.process_content(target_content, command_type)
            
            await thinking_msg.edit_text(response)
            
        except Exception as e:
            error_msg = format_error_message("CONTENT_ERROR", str(e))
            await message.edit_text(error_msg)
    
    async def process_analysis_command(self, message: Message, command_type: str):
        """Process analysis commands"""
        try:
            thinking_msg = await message.edit_text("checking this out...")
            await asyncio.sleep(1)
            
            target_content = await self.get_target_content(message)
            if not target_content:
                await thinking_msg.edit_text("need something to analyze - reply to a message or include some text")
                return
            
            response = await self.gemini.analyze_content(target_content, command_type)
            
            await thinking_msg.edit_text(response)
            
        except Exception as e:
            error_msg = format_error_message("ANALYSIS_ERROR", str(e))
            await message.edit_text(error_msg)
    
    async def process_search_command(self, message: Message):
        """Search through chat history"""
        try:
            thinking_msg = await message.edit_text("🔍 **Searching chat history...**")
            await asyncio.sleep(1)
            
            query = message.text.replace(".search", "").strip()
            if not query:
                await thinking_msg.edit_text("❌ Please provide a search query. Usage: `.search your query`")
                return
            
            # Search chat history
            with app.app_context():
                results = ChatHistory.query.filter(
                    ChatHistory.chat_id == message.chat.id,
                    ChatHistory.message_text.ilike(f"%{query}%")
                ).order_by(ChatHistory.timestamp.desc()).limit(10).all()
            
            if not results:
                await thinking_msg.edit_text(f"🔍 **Search Results**\n\nNo messages found containing: `{query}`")
                return
            
            # Format results
            search_results = f"🔍 **Search Results for:** `{query}`\n\n"
            for result in results:
                date_str = result.timestamp.strftime("%Y-%m-%d %H:%M")
                user_info = result.first_name or result.username or "Unknown"
                text_preview = (result.message_text[:100] + "...") if len(result.message_text) > 100 else result.message_text
                search_results += f"**{date_str}** - {user_info}:\n{text_preview}\n\n"
            
            search_results += "✨ *Powered by Envologia*"
            await thinking_msg.edit_text(search_results)
            
        except Exception as e:
            error_msg = format_error_message("SEARCH_ERROR", str(e))
            await message.edit_text(error_msg)
    
    async def process_roleplay_command(self, message: Message):
        """Start roleplay mode"""
        try:
            character = message.text.replace(".roleplay", "").strip()
            if not character:
                await message.edit_text("🎭 **Roleplay Mode**\n\nUsage: `.roleplay [character name]`\nExample: `.roleplay Sherlock Holmes`")
                return
            
            # Store roleplay context
            with app.app_context():
                user_context = UserContext.query.filter_by(user_id=message.from_user.id).first()
                if not user_context:
                    user_context = UserContext(user_id=message.from_user.id)
                    db.session.add(user_context)
                
                user_context.current_roleplay = character
                user_context.last_interaction = datetime.utcnow()
                db.session.commit()
            
            await message.edit_text(f"🎭 **Roleplay Mode Activated**\n\nI am now roleplaying as: **{character}**\n\nUse `.ask` to interact with me as this character.\nUse `.clear` to exit roleplay mode.\n\n✨ *Powered by Envologia*")
            
        except Exception as e:
            error_msg = format_error_message("ROLEPLAY_ERROR", str(e))
            await message.edit_text(error_msg)
    
    async def process_clear_command(self, message: Message):
        """Clear roleplay mode and context"""
        try:
            with app.app_context():
                user_context = UserContext.query.filter_by(user_id=message.from_user.id).first()
                if user_context:
                    user_context.current_roleplay = None
                    user_context.conversation_context = None
                    db.session.commit()
            
            await message.edit_text("cleared context and roleplay mode")
            
        except Exception as e:
            error_msg = format_error_message("CLEAR_ERROR", str(e))
            await message.edit_text(error_msg)
    
    async def process_help_command(self, message: Message):
        """Show the help message with all available commands."""
        help_text = """**Envo AI Userbot Commands:**

**AI & Questions:**
• `.ask [question]` - Ask the AI anything.
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
            await message.edit_text(help_text)
        except Exception as e:
            logger.error(f"Failed to send help message: {e}")
            await message.edit_text("Sorry, couldn't fetch the help menu right now.")

    async def get_message_context(self, message: Message):
        """Get context for the message"""
        context_parts = []
        
        # Check if replying to a message
        if message.reply_to_message:
            reply_msg = message.reply_to_message
            
            # Handle different message types
            if reply_msg.text:
                context_parts.append(f"Replied message: {reply_msg.text}")
            elif reply_msg.photo:
                # Analyze image
                try:
                    photo_path = await self.client.download_media(reply_msg.photo)
                    analysis = await analyze_image(photo_path)
                    context_parts.append(f"Image content: {analysis}")
                    os.remove(photo_path)  # Clean up
                except Exception as e:
                    logger.error(f"Image analysis error: {e}")
                    context_parts.append("Image: Could not analyze")
            elif reply_msg.voice:
                # Transcribe voice
                try:
                    voice_path = await self.client.download_media(reply_msg.voice)
                    transcription = await transcribe_voice(voice_path)
                    context_parts.append(f"Voice message: {transcription}")
                    os.remove(voice_path)  # Clean up
                except Exception as e:
                    logger.error(f"Voice transcription error: {e}")
                    context_parts.append("Voice: Could not transcribe")
        
        # Get recent chat context
        chat_context = await get_chat_context(message.chat.id, limit=5)
        if chat_context:
            context_parts.append(f"Recent chat: {chat_context}")
        
        return "\n".join(context_parts) if context_parts else None
    
    async def get_target_content(self, message: Message):
        """Get content to process from command or reply"""
        # First check if there's content after the command
        command_parts = message.text.split(" ", 1)
        if len(command_parts) > 1 and command_parts[1].strip():
            return command_parts[1].strip()
        
        # Check if replying to a message
        if message.reply_to_message:
            reply_msg = message.reply_to_message
            if reply_msg.text:
                return reply_msg.text
            # Handle other message types if needed
        
        return None
    
    async def store_chat_history(self, message: Message):
        """Store message in chat history for context"""
        try:
            with app.app_context():
                # Don't store command messages
                if message.text and message.text.startswith('.'):
                    return
                
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

# For backward compatibility with app.py imports
userbot_manager = None

def start_userbot_background():
    """Start userbot in background - for compatibility"""
    pass  # This is handled by app.py now
