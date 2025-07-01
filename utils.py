import os
import logging
import asyncio
import speech_recognition as sr
from PIL import Image
from app import app
from models import ChatHistory

logger = logging.getLogger(__name__)

async def transcribe_voice(voice_path: str):
    """Transcribe voice message to text"""
    try:
        # Run transcription in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _transcribe_sync, voice_path)
    except Exception as e:
        logger.error(f"Voice transcription error: {e}")
        return "Could not transcribe voice message"

def _transcribe_sync(voice_path: str):
    """Synchronous voice transcription"""
    try:
        recognizer = sr.Recognizer()
        
        # Convert to WAV if needed (speech_recognition works better with WAV)
        with sr.AudioFile(voice_path) as source:
            audio = recognizer.record(source)
            
        # Try Google Speech Recognition
        try:
            text = recognizer.recognize_google(audio)
            return text
        except sr.UnknownValueError:
            return "Could not understand audio"
        except sr.RequestError:
            # Fallback to other recognition methods
            try:
                text = recognizer.recognize_sphinx(audio)
                return text
            except:
                return "Speech recognition service unavailable"
                
    except Exception as e:
        logger.error(f"Sync transcription error: {e}")
        return "Error transcribing audio"

async def analyze_image(image_path: str):
    """Analyze image and extract text"""
    try:
        # Import here to avoid circular imports
        from gemini_client import GeminiClient
        
        gemini = GeminiClient()
        analysis = await gemini.analyze_image(image_path)
        return analysis
        
    except Exception as e:
        logger.error(f"Image analysis error: {e}")
        return "Could not analyze image"

async def get_chat_context(chat_id: int, limit: int = 10):
    """Get recent chat context for AI responses"""
    try:
        with app.app_context():
            recent_messages = ChatHistory.query.filter_by(chat_id=chat_id).order_by(
                ChatHistory.timestamp.desc()
            ).limit(limit).all()
            
            if not recent_messages:
                return None
            
            context_messages = []
            for msg in reversed(recent_messages):  # Get chronological order
                if msg.message_text and not (msg.message_text.startswith('.') and msg.user_id):
                    user_info = msg.first_name or msg.username or "User"
                    timestamp = msg.timestamp.strftime("%H:%M")
                    context_messages.append(f"[{timestamp}] {user_info}: {msg.message_text}")
            
            return "\n".join(context_messages[-5:]) if context_messages else None  # Last 5 messages
            
    except Exception as e:
        logger.error(f"Context retrieval error: {e}")
        return None

def format_error_message(error_type: str, error_details: str):
    """Format themed error messages"""
    error_messages = {
        "AI_ERROR": "🤖 **AI Processing Error**\n\nEnvo encountered an issue while generating your response:",
        "CONTENT_ERROR": "📝 **Content Processing Error**\n\nCouldn't process the requested content:",
        "ANALYSIS_ERROR": "🔬 **Analysis Error**\n\nFailed to analyze the provided content:",
        "SEARCH_ERROR": "🔍 **Search Error**\n\nEncountered an issue while searching:",
        "ROLEPLAY_ERROR": "🎭 **Roleplay Error**\n\nCouldn't activate roleplay mode:",
        "CLEAR_ERROR": "🧹 **Clear Context Error**\n\nFailed to clear context:",
        "TRANSCRIPTION_ERROR": "🎵 **Voice Transcription Error**\n\nCouldn't process voice message:",
        "IMAGE_ERROR": "🖼️ **Image Analysis Error**\n\nFailed to analyze image:",
        "RATE_LIMIT_ERROR": "⏰ **Rate Limit Error**\n\nToo many requests. Please wait a moment:",
        "NETWORK_ERROR": "🌐 **Network Error**\n\nConnection issue detected:",
        "API_ERROR": "🔑 **API Error**\n\nService temporarily unavailable:"
    }
    
    base_message = error_messages.get(error_type, "❌ **Unknown Error**\n\nAn unexpected error occurred:")
    
    return f"{base_message}\n\n`{error_details}`\n\n💡 **Troubleshooting:**\n• Try again in a few moments\n• Check your command syntax\n• Ensure you have proper permissions\n\n✨ *Powered by Envologia*"

async def check_rate_limit(user_id: int, chat_id: int):
    """Check if user is rate limited"""
    try:
        from datetime import datetime, timedelta
        from models import CommandQueue
        
        with app.app_context():
            # Check recent commands in last minute
            recent_time = datetime.utcnow() - timedelta(minutes=1)
            recent_commands = CommandQueue.query.filter(
                CommandQueue.user_id == user_id,
                CommandQueue.created_at > recent_time
            ).count()
            
            # Allow max 10 commands per minute
            if recent_commands >= 10:
                return False, "Rate limit exceeded. Please wait before sending more commands."
            
            return True, None
            
    except Exception as e:
        logger.error(f"Rate limit check error: {e}")
        return True, None  # Allow on error

def clean_old_data():
    """Clean old chat history and command queue data"""
    try:
        from datetime import datetime, timedelta
        
        with app.app_context():
            # Delete chat history older than 30 days
            old_date = datetime.utcnow() - timedelta(days=30)
            ChatHistory.query.filter(ChatHistory.timestamp < old_date).delete()
            
            # Delete completed command queue entries older than 1 day
            queue_old_date = datetime.utcnow() - timedelta(days=1)
            from models import CommandQueue
            CommandQueue.query.filter(
                CommandQueue.processed_at < queue_old_date,
                CommandQueue.status.in_(['completed', 'failed'])
            ).delete()
            
            db.session.commit()
            logger.info("Cleaned old data successfully")
            
    except Exception as e:
        logger.error(f"Data cleanup error: {e}")
