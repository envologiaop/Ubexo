import os
import logging
import requests
import google.generativeai as genai

from app import app
from models import ChatHistory

# Configure logging
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

    async def _search_with_tavily(self, query: str):
        """Perform a web search using the Tavily Search API."""
        tavily_api_key = os.environ.get("TAVILY_API_KEY")
        if not tavily_api_key:
            logger.warning("TAVILY_API_KEY not set. Live search is disabled.")
            return "Live search is not configured."

        try:
            response = requests.post("https://api.tavily.com/search", json={
                "api_key": tavily_api_key,
                "query": query,
                "search_depth": "basic",
                "include_answer": True,
                "max_results": 3
            })
            response.raise_for_status()
            data = response.json()
            return data.get("answer") or "\n".join([r['snippet'] for r in data.get("results", [])])
        except Exception as e:
            logger.error(f"Tavily search error: {e}")
            return f"Sorry, I couldn't perform a live search due to an error: {e}"

    def _needs_current_info(self, question: str):
        """Check if a question likely requires real-time information."""
        current_indicators = [
            'latest', 'new', 'recent', 'current', 'today', 'now', 'this year',
            '2024', '2025', 'trending', 'breaking', 'updated', 'news', 'score',
            'price', 'time', 'weather', 'who is', 'what is the current'
        ]
        return any(indicator in question.lower() for indicator in current_indicators)

    async def generate_response(self, question: str, replied_content: str = None, chat_id: int = None):
        """Generate AI response with a compatible prompt structure."""
        try:
            system_prompt = """You are me - respond as if YOU are the actual person whose Telegram account this is.

CONTEXT RULES:
- If the user's request is a reply to a message, that replied-to text is the primary subject. Your answer MUST be based on that subject. For example, if the user replies to "London" and asks "what time is it?", you must answer for London. Do not ask for the city again.
- Use 'Live Search Results' as the source of truth for real-time questions.
- Use 'Recent Chat History' only for conversational context, not as the main subject when a reply is present.

PERSONALITY:
- Casual, friendly, and natural. Give personal opinions and use casual grammar.

NEVER:
- Never say you're an AI, bot, or assistant.
- Never use formal or corporate language.
"""
            search_query = f"{question} {replied_content}" if replied_content else question
            search_results = None
            if self._needs_current_info(search_query):
                search_results = await self._search_with_tavily(search_query)

            user_prompt_parts = []
            if replied_content:
                user_prompt_parts.append(f"The primary subject of my question is this text:\n---\n{replied_content}\n---")

            user_prompt_parts.append(f"My question/request is: {question}")
            
            if search_results:
                user_prompt_parts.append(f"Use this live search result as the primary source of truth to answer:\n---\n{search_results}\n---")

            chat_context = await self._get_recent_context(chat_id)
            if chat_context:
                user_prompt_parts.append(f"For background, here is the recent chat history:\n{chat_context}")
            
            final_user_prompt = "\n\n".join(user_prompt_parts)

            # --- MODIFICATION START ---
            # For older library versions, the system prompt must be part of the main contents list.
            request_contents = [
                {
                    "role": "system",
                    "parts": [system_prompt]
                },
                {
                    "role": "user",
                    "parts": [final_user_prompt]
                }
            ]

            # The generate_content call no longer has the system_instruction argument.
            response = self.model.generate_content(
                contents=request_contents
            )
            # --- MODIFICATION END ---
            
            # The .text attribute may not exist on older response objects.
            # We access the text more safely.
            response_text = ""
            if response.parts:
                response_text = response.parts[0].text

            return response_text or "hmm, something went wrong there. try again?"

        except Exception as e:
            logger.error(f"Gemini API error: {e}", exc_info=True)
            return "having some trouble right now, try again in a moment"

    # Other functions...
    
    async def _get_recent_context(self, chat_id: int, limit: int = 5):
        """Get recent chat context from the database."""
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
