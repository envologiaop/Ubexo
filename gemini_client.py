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
        except Exception as e:
            logger.error(f"Error during GeminiClient initialization: {e}")
            raise

    # ... (other functions like _search_with_tavily and _needs_current_info remain the same) ...

    async def generate_response(self, question: str, replied_content: str = None, chat_id: int = None):
        """Generate AI response with the OLDER compatible prompt structure."""
        try:
            system_prompt = """You are me - respond as if YOU are the actual person whose Telegram account this is...""" # Your full prompt here
            
            # ... (the logic to build user_prompt_parts remains the same) ...
            user_prompt_parts = []
            if replied_content:
                user_prompt_parts.append(f"The primary subject of my question is this text:\n---\n{replied_content}\n---")
            user_prompt_parts.append(f"My question/request is: {question}")
            # ... (add search results and chat context if they exist) ...
            final_user_prompt = "\n\n".join(user_prompt_parts)

            # --- THIS IS THE FIX FOR THE OLD LIBRARY VERSION ---
            # We combine the system and user prompts and pass them together.
            full_prompt = f"{system_prompt}\n\n{final_user_prompt}"
            
            # The older method `generate_text` is used on the `genai` module directly.
            response = genai.generate_text(
                model='models/gemini-1.5-flash-latest',
                prompt=full_prompt,
                temperature=0.7
            )
            
            # Access the result from the response object
            return response.result or "hmm, something went wrong there. try again?"
            # --- END OF FIX ---

        except Exception as e:
            logger.error(f"Gemini API error: {e}", exc_info=True)
            return "having some trouble right now, try again in a moment"

    # ... (the rest of the file remains the same) ...
