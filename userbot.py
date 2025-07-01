import os
import asyncio
import logging
import threading
import time
from datetime import datetime, timedelta

# Import pyrogram components carefully to avoid sync module issues
try:
    from pyrogram import Client
    from pyrogram import filters
    from pyrogram.types import Message
except ImportError as e:
    logging.error(f"Failed to import pyrogram: {e}")
    raise

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
        
    async def stop(self):
        """Gracefully stop the userbot"""
        try:
            logger.info("Stopping userbot...")
            self.is_running = False
            
            if self.client and hasattr(self.client, 'is_connected') and self.client.is_connected:
                await self.client.stop()
                logger.info("Userbot stopped successfully")
        except Exception as e:
            logger.error(f"Error stopping userbot: {e}")
        
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
            # Simple command that does nothing - useful for testing
            await message.edit_text("✓")
            
        # Store all messages for context (excluding commands to avoid loops)
        @self.client.on_message(~filters.me & ~filters.bot)
        async def store_message(client, message: Message):
            await self.store_chat_history(message)

    async def start(self):
        """Start the userbot with comprehensive error handling"""
        startup_attempts = 0
        max_startup_attempts = 3
        
        while startup_attempts < max_startup_attempts:
            try:
                startup_attempts += 1
                logger.info(f"Initializing Telegram userbot (attempt {startup_attempts}/{max_startup_attempts})...")
                
                await self.initialize_client()
                
                logger.info("Starting Telegram client...")
                await self.client.start()
                
                self.is_running = True
                logger.info("✅ Envo userbot started successfully! Ready to respond in Telegram.")
                
                # Keep the client running with improved handling
                try:
                    # Try the standard idle method first
                    await self.client.idle()
                except (AttributeError, NotImplementedError, RuntimeError) as e:
                    logger.info(f"Standard idle not available ({e}), using custom keep-alive...")
                    
                    # Custom keep-alive loop for deployment environments
                    try:
                        while self.is_running:
                            # Check if client is still connected
                            if hasattr(self.client, 'is_connected') and not self.client.is_connected:
                                logger.warning("Client disconnected, attempting reconnect...")
                                try:
                                    await self.client.start()
                                except Exception as reconnect_error:
                                    logger.error(f"Reconnection failed: {reconnect_error}")
                                    break
                            
                            # Sleep with cancellation support
                            await asyncio.sleep(5)
                            
                    except asyncio.CancelledError:
                        logger.info("Userbot keep-alive cancelled")
                        break
                    except Exception as keep_alive_error:
                        logger.error(f"Keep-alive error: {keep_alive_error}")
                        break
                
                # If we reach here, userbot stopped normally
                break
                
            except Exception as e:
                logger.error(f"Failed to start userbot (attempt {startup_attempts}): {e}")
                self.is_running = False
                
                if startup_attempts >= max_startup_attempts:
                    logger.error("Max startup attempts reached, giving up")
                    raise
                else:
                    logger.info(f"Retrying in 5 seconds...")
                    await asyncio.sleep(5)
            
            finally:
                # Ensure proper cleanup
                if hasattr(self, 'client') and self.client:
                    try:
                        if hasattr(self.client, 'is_connected') and self.client.is_connected:
                            await self.client.stop()
                    except Exception as cleanup_error:
                        logger.error(f"Error during client cleanup: {cleanup_error}")
                
                self.is_running = False
            
    async def process_ask_command(self, message: Message):
        """Process .ask command with AI response"""
        try:
            # Get the question from command arguments
            question = message.text.split(' ', 1)[1] if len(message.text.split(' ')) > 1 else None
            
            if not question:
                await message.edit_text("Please provide a question. Usage: `.ask your question here`")
                return
                
            # Show typing indicator
            await message.edit_text("💭")
            
            # Get context for better responses
            context = await self.get_message_context(message)
            
            # Generate AI response
            response = await self.gemini.generate_response(question, context, message.chat.id)
            
            if response:
                await message.edit_text(response)
            else:
                await message.edit_text("Sorry, I couldn't generate a response right now.")
                
        except Exception as e:
            error_msg = format_error_message("AI Response", str(e))
            await message.edit_text(error_msg)
            logger.error(f"Ask command error: {e}")
            
    async def process_content_command(self, message: Message, command_type: str):
        """Process content creation commands"""
        try:
            # Get content to process
            content = await self.get_target_content(message)
            
            if not content:
                await message.edit_text(f"Please provide content to {command_type}. Reply to a message or provide text after the command.")
                return
                
            # Show processing indicator
            await message.edit_text("⚡")
            
            # Process with AI
            result = await self.gemini.process_content(content, command_type)
            
            if result:
                await message.edit_text(result)
            else:
                await message.edit_text(f"Couldn't {command_type} the content right now.")
                
        except Exception as e:
            error_msg = format_error_message("Content Processing", str(e))
            await message.edit_text(error_msg)
            logger.error(f"{command_type} command error: {e}")
            
    async def process_analysis_command(self, message: Message, command_type: str):
        """Process analysis commands"""
        try:
            # Get content to analyze
            content = await self.get_target_content(message)
            
            if not content:
                await message.edit_text(f"Please provide content to {command_type}. Reply to a message or provide text after the command.")
                return
                
            # Show processing indicator
            await message.edit_text("🔍")
            
            # Analyze with AI
            result = await self.gemini.analyze_content(content, command_type)
            
            if result:
                await message.edit_text(result)
            else:
                await message.edit_text(f"Couldn't {command_type} the content right now.")
                
        except Exception as e:
            error_msg = format_error_message("Content Analysis", str(e))
            await message.edit_text(error_msg)
            logger.error(f"{command_type} command error: {e}")
            
    async def process_search_command(self, message: Message):
        """Search through chat history"""
        try:
            # Get search query
            query = message.text.split(' ', 1)[1] if len(message.text.split(' ')) > 1 else None
            
            if not query:
                await message.edit_text("Please provide a search query. Usage: `.search your query`")
                return
                
            await message.edit_text("🔍")
            
            # Search chat history
            with app.app_context():
                results = ChatHistory.query.filter(
                    ChatHistory.chat_id == message.chat.id,
                    ChatHistory.message_text.ilike(f'%{query}%')
                ).order_by(ChatHistory.timestamp.desc()).limit(5).all()
                
            if results:
                search_results = "🔍 **Search Results:**\n\n"
                for result in results:
                    user_name = result.first_name or result.username or "Unknown"
                    date = result.timestamp.strftime("%Y-%m-%d %H:%M")
                    text = result.message_text[:100] + "..." if len(result.message_text) > 100 else result.message_text
                    search_results += f"**{user_name}** ({date}):\n{text}\n\n"
                    
                await message.edit_text(search_results)
            else:
                await message.edit_text(f"No messages found containing '{query}'")
                
        except Exception as e:
            error_msg = format_error_message("Search", str(e))
            await message.edit_text(error_msg)
            logger.error(f"Search command error: {e}")
            
    async def process_roleplay_command(self, message: Message):
        """Start roleplay mode"""
        try:
            character = message.text.split(' ', 1)[1] if len(message.text.split(' ')) > 1 else None
            
            if not character:
                await message.edit_text("Please specify a character. Usage: `.roleplay character name`")
                return
                
            # Save roleplay context
            with app.app_context():
                user_context = UserContext.query.filter_by(user_id=message.from_user.id).first()
                if not user_context:
                    user_context = UserContext(user_id=message.from_user.id)
                    db.session.add(user_context)
                    
                user_context.current_roleplay = character
                user_context.last_interaction = datetime.utcnow()
                db.session.commit()
                
            await message.edit_text(f"🎭 Now roleplaying as **{character}**. Use `.clear` to stop.")
            
        except Exception as e:
            error_msg = format_error_message("Roleplay", str(e))
            await message.edit_text(error_msg)
            logger.error(f"Roleplay command error: {e}")
            
    async def process_clear_command(self, message: Message):
        """Clear roleplay mode and context"""
        try:
            with app.app_context():
                user_context = UserContext.query.filter_by(user_id=message.from_user.id).first()
                if user_context:
                    user_context.current_roleplay = None
                    user_context.conversation_context = None
                    db.session.commit()
                    
            await message.edit_text("🧹 Context cleared. Back to normal mode.")
            
        except Exception as e:
            error_msg = format_error_message("Clear", str(e))
            await message.edit_text(error_msg)
            logger.error(f"Clear command error: {e}")
            
    async def process_help_command(self, message: Message):
        """Show help information"""
        help_text = """
🤖 **Envo AI Userbot Commands**

**💬 AI Interaction:**
• `.ask [question]` - Ask AI anything
• `.roleplay [character]` - Start roleplay mode

**📝 Content Tools:**
• `.summarize` - Summarize content (reply to message)
• `.translate` - Translate text
• `.rewrite` - Rewrite in different style
• `.improve` - Enhance text quality
• `.expand` - Add more detail
• `.condense` - Make more concise

**🔍 Analysis:**
• `.analyze` - Analyze content
• `.explain` - Explain concepts
• `.search [query]` - Search chat history

**⚙️ Utilities:**
• `.clear` - Clear roleplay/context
• `.help` - Show this help
• `.pass` - Simple test command

**📱 Usage:**
Reply to a message or add text after commands. Envo remembers conversations and responds naturally like you.
        """
        await message.edit_text(help_text)

    async def get_message_context(self, message: Message):
        """Get context for the message"""
        try:
            # Get recent chat context
            context = await get_chat_context(message.chat.id)
            
            # Get user roleplay context if any
            with app.app_context():
                user_context = UserContext.query.filter_by(user_id=message.from_user.id).first()
                if user_context and user_context.current_roleplay:
                    context += f"\n\nCurrently roleplaying as: {user_context.current_roleplay}"
                    
            return context
            
        except Exception as e:
            logger.error(f"Error getting message context: {e}")
            return ""
            
    async def get_target_content(self, message: Message):
        """Get content to process from command or reply"""
        try:
            # Check if replying to a message
            if message.reply_to_message:
                reply_msg = message.reply_to_message
                
                # Handle different message types
                if reply_msg.text:
                    return reply_msg.text
                elif reply_msg.voice:
                    # Download and transcribe voice
                    voice_path = await reply_msg.download()
                    return await transcribe_voice(voice_path)
                elif reply_msg.photo:
                    # Download and analyze image
                    image_path = await reply_msg.download()
                    return await analyze_image(image_path)
                else:
                    return "Media content that needs processing"
                    
            # Check for text after command
            command_parts = message.text.split(' ', 1)
            if len(command_parts) > 1:
                return command_parts[1]
                
            return None
            
        except Exception as e:
            logger.error(f"Error getting target content: {e}")
            return None
            
    async def store_chat_history(self, message: Message):
        """Store message in chat history for context"""
        try:
            with app.app_context():
                chat_entry = ChatHistory(
                    chat_id=message.chat.id,
                    message_id=message.id,
                    user_id=message.from_user.id if message.from_user else None,
                    username=message.from_user.username if message.from_user else None,
                    first_name=message.from_user.first_name if message.from_user else None,
                    last_name=message.from_user.last_name if message.from_user else None,
                    message_text=message.text or message.caption,
                    message_type=self.get_message_type(message),
                    file_id=self.get_file_id(message),
                    reply_to_message_id=message.reply_to_message.id if message.reply_to_message else None,
                    timestamp=datetime.utcnow()
                )
                
                db.session.add(chat_entry)
                db.session.commit()
                
        except Exception as e:
            logger.error(f"Error storing chat history: {e}")
            
    def get_message_type(self, message: Message):
        """Determine message type"""
        if message.text:
            return "text"
        elif message.photo:
            return "photo"
        elif message.voice:
            return "voice"
        elif message.video:
            return "video"
        elif message.document:
            return "document"
        else:
            return "other"
            
    def get_file_id(self, message: Message):
        """Get file ID if message contains media"""
        if message.photo:
            return message.photo.file_id
        elif message.voice:
            return message.voice.file_id
        elif message.video:
            return message.video.file_id
        elif message.document:
            return message.document.file_id
        return None

def start_userbot_background():
    """Start userbot in background - for compatibility"""
    def run_userbot():
        try:
            manager = UserbotManager()
            asyncio.run(manager.start())
        except Exception as e:
            logger.error(f"Background userbot error: {e}")
    
    thread = threading.Thread(target=run_userbot, daemon=True)
    thread.start()
    return thread