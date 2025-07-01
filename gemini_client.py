import os
import logging
import google.generativeai as genai
from app import app
from models import ChatHistory

logger = logging.getLogger(__name__)

class GeminiClient:
    def __init__(self):
        try:
            self.api_key = os.environ.get("GEMINI_API_KEY")
            if not self.api_key:
                raise ValueError("GEMINI_API_KEY environment variable not set.")
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel('gemini-1.5-flash')
        except AttributeError:
            logger.error("Failed to initialize GeminiClient. Your google-generativeai library is likely outdated.")
            raise
        except Exception as e:
            logger.error(f"Error during GeminiClient initialization: {e}")
            raise

    def needs_current_info(self, question: str):
        """Check if question needs current/recent information"""
        current_indicators = [
            'latest', 'new', 'recent', 'current', 'today', 'now', 'this year',
            '2024', '2025', 'trending', 'breaking', 'updated', 'news', 'score', 'price', 'time'
        ]
        return any(indicator in question.lower() for indicator in current_indicators)

    async def generate_response(self, question: str, replied_content: str = None, chat_id: int = None):
        """Generate AI response with a clear, prioritized prompt structure."""
        try:
            system_prompt = """You are me - respond as if YOU are the actual person whose Telegram account this is.

CONTEXT RULES:
- When the user's request is based on a replied-to message, that text is the primary subject.
- Your answer MUST be based on that subject. For example, if the user replies to "London" and asks "what time is it?", you must answer for London. Do not ask for the city again.
- Use the 'Recent Chat History' only for conversational context, not as the main subject when a reply is present.

PERSONALITY:
- Casual, friendly, and natural. Give personal opinions and use casual grammar.

NEVER:
- Never say you're an AI, bot, or assistant.
- Never use formal or corporate language.
"""
            user_prompt_parts = []
            if replied_content:
                user_prompt_parts.append(f"The primary subject of my question is the following text:\n---\n{replied_content}\n---")

            user_prompt_parts.append(f"My question about the subject is: {question}")

            chat_context = await self.get_recent_context(chat_id)
            if chat_context:
                user_prompt_parts.append(f"For background, here is the recent chat history:\n{chat_context}")
            
            final_user_prompt = "\n\n".join(user_prompt_parts)

            # **MODIFICATION START**
            # This is a simplified and more compatible way to send the request,
            # avoiding the `types.Content` and `types.Part` objects.
            request_contents = [
                {
                    "role": "user",
                    "parts": [final_user_prompt]
                }
            ]

            response = self.model.generate_content(
                contents=request_contents,
                system_instruction=system_prompt
            )
            # **MODIFICATION END**
            
            return response.text or "hmm, something went wrong there. try again?"

        except Exception as e:
            logger.error(f"Gemini API error: {e}", exc_info=True)
            return "having some trouble right now, try again in a moment"

    # Other functions like process_content can be simplified similarly if needed,
    # but the generate_response is the one causing your current error.

    async def get_recent_context(self, chat_id: int, limit: int = 5):
        """Get recent chat context for better responses"""
        if not chat_id:
            return None
        try:
            with app.app_context():
                recent_messages = ChatHistory.query.filter_by(chat_id=chat_id).order_by(
                    ChatHistory.timestamp.desc()
                ).limit(limit).all()
                
                if not recent_messages:
                    return None
                
                context_parts = []
                for msg in reversed(recent_messages):
                    if msg.message_text:
                        user_info = msg.first_name or "User"
                        context_parts.append(f"{user_info}: {msg.message_text}")
                
                return "\n".join(context_parts) if context_parts else None
        except Exception as e:
            logger.error(f"Context retrieval error: {e}")
            return None
