import os
import logging
import requests
import google.generativeai as genai
from google.generativeai import types
from app import app
from models import ChatHistory

logger = logging.getLogger(__name__)

class GeminiClient:
    def __init__(self):
        # Ensure you have the google.generativeai package installed
        try:
            self.client = genai.GenerativeModel('gemini-1.5-flash')
            genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
        except ImportError:
            raise ImportError("Please install google-generativeai for GeminiClient to work.")
        
    async def search_current_info(self, query: str):
        # This function can be improved, but is okay for now.
        # A proper search API would be better.
        return None

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
            # **MODIFICATION START**
            # A new, more direct system prompt.
            system_prompt = """You are me - respond as if YOU are the actual person whose Telegram account this is.

CONTEXT RULES:
- When the user's request is based on a replied-to message, that text is the primary subject.
- Your answer MUST be based on that subject. For example, if the user replies to "London" and asks "what time is it?", you must answer for London. Do not ask for the city again.
- Use the 'Recent Chat History' only for conversational context, not as the main subject when a reply is present.

PERSONALITY:
- Casual, friendly, and natural.
- Give personal opinions and use casual grammar (slang, abbreviations) when it feels right.

NEVER:
- Never say you're an AI, bot, or assistant.
- Never use formal or corporate language.
"""

            # Combine the question and replied content for a more effective search
            search_query = f"{question} {replied_content}" if replied_content else question
            search_results = None
            if self.needs_current_info(search_query):
                search_results = await self.search_current_info(search_query)

            # Build a clear, structured user prompt
            user_prompt_parts = []
            if replied_content:
                user_prompt_parts.append(f"The primary subject of my question is the following text:\n---\n{replied_content}\n---")

            user_prompt_parts.append(f"My question about the subject is: {question}")
            
            if search_results:
                user_prompt_parts.append(f"Here is some real-time info to help answer:\n{search_results}")

            chat_context = await self.get_recent_context(chat_id)
            if chat_context:
                user_prompt_parts.append(f"For background, here is the recent chat history:\n{chat_context}")
            
            final_user_prompt = "\n\n".join(user_prompt_parts)

            response = self.client.generate_content(
                contents=[
                    types.Content(
                        role="user",
                        parts=[types.Part(text=final_user_prompt)]
                    )
                ],
                generation_config=types.GenerationConfig(
                    temperature=0.7
                ),
                system_instruction=types.Content(
                    role="system",
                    parts=[types.Part(text=system_prompt)]
                )
            )
            
            return response.text or "hmm, something went wrong there. try again?"
            # **MODIFICATION END**

        except Exception as e:
            logger.error(f"Gemini API error: {e}", exc_info=True)
            return "having some trouble right now, try again in a moment"
    
    async def process_content(self, content: str, command_type: str):
        """Process content based on command type"""
        # This function remains the same
        try:
            prompts = {
                "summarize": f"Summarize this naturally like you're explaining it to someone:\n\n{content}",
                "translate": f"Translate this naturally, as if you speak both languages fluently:\n\n{content}",
                "rewrite": f"Rewrite this with your own personal style and voice:\n\n{content}",
                "improve": f"Make this better - fix grammar, improve flow, make it sound more natural:\n\n{content}",
                "expand": f"Expand on this with more information and examples:\n\n{content}",
                "condense": f"Make this more concise but keep all the important stuff:\n\n{content}"
            }
            prompt = prompts.get(command_type)
            natural_system = "Respond as the actual person whose account this is. Be natural, casual, and human-like. Don't sound like an AI."
            
            response = self.client.generate_content(
                contents=[types.Content(role="user", parts=[types.Part(text=prompt)])],
                system_instruction=types.Content(role="system", parts=[types.Part(text=natural_system)])
            )
            return response.text or "couldn't process that, try again"
        except Exception as e:
            logger.error(f"Content processing error: {e}")
            return f"something's not working right: {str(e)}"
    
    async def analyze_content(self, content: str, command_type: str):
        """Analyze content based on command type"""
        # This function remains the same
        try:
            prompts = {
                "analyze": f"Analyze this naturally - what are the key points, themes, and what do you think about it?:\n\n{content}",
                "explain": f"Explain this like you're talking to a friend who needs to understand it:\n\n{content}"
            }
            prompt = prompts.get(command_type)
            natural_system = "You are the actual person whose account this is. Give your genuine thoughts and analysis in a casual, conversational way."
            
            response = self.client.generate_content(
                contents=[types.Content(role="user", parts=[types.Part(text=prompt)])],
                system_instruction=types.Content(role="system", parts=[types.Part(text=natural_system)])
            )
            return response.text or "couldn't analyze that properly, try again"
        except Exception as e:
            logger.error(f"Content analysis error: {e}")
            return f"analysis failed: {str(e)}"

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
