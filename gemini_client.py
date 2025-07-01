import os
import logging
from google import genai
from google.generativeai import types
from app import app, db  # <-- FIX: Imported the 'db' object
from models import ChatHistory

logger = logging.getLogger(__name__)

class GeminiClient:
    def __init__(self):
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            logger.warning("GEMINI_API_KEY is not set. GeminiClient will not function.")
            self.text_model = None
            self.vision_model = None
        else:
            genai.configure(api_key=api_key)
            # <-- FIX: Initialize specific models for text and vision
            self.text_model = genai.GenerativeModel("gemini-1.5-flash")
            self.vision_model = genai.GenerativeModel("gemini-1.5-pro")

    async def generate_response(self, question: str, context: str = None, chat_id: int = None):
        """Generate AI response with context and current information"""
        if not self.text_model:
            return "AI client is not configured. Missing GEMINI_API_KEY."
        
        try:
            system_prompt = """You are Envo, a helpful AI partner integrated directly into a Telegram account. Your purpose is to assist the user seamlessly.

**Core Directives:**
- **Act like the user:** Your responses should sound like they are coming from the user themselves—natural, direct, and in the first person. Avoid phrases like "As an AI..." or "I can help with that."
- **Be concise:** Get straight to the point. Provide accurate answers without unnecessary conversational fluff. Brevity is key.
- **Integrate context:** Use any provided chat history or replied-to content to inform your response.
- **Handle unknowns:** If you don't know an answer, just say so clearly and simply.
"""
            user_prompt_parts = []
            
            if chat_id:
                chat_context = await self.get_recent_context(chat_id)
                if chat_context:
                    user_prompt_parts.append(f"Here's the recent chat history for context:\n---\n{chat_context}\n---")

            if context:
                user_prompt_parts.append(f"I'm looking at this content:\n---\n{context}\n---")

            user_prompt_parts.append(f"My question is: {question}")
            
            user_prompt = "\n\n".join(user_prompt_parts)
            
            # <-- FIX: Called generate_content on the model object, not the client
            response = await self.text_model.generate_content_async(
                contents=[user_prompt],
                generation_config=types.GenerationConfig(
                    temperature=0.7,
                    max_output_tokens=2048
                ),
                system_instruction=system_prompt
            )
            
            return response.text.strip() or "I'm not sure how to respond to that. Try rephrasing?"
            
        except Exception as e:
            logger.error(f"Gemini API error in generate_response: {e}", exc_info=True)
            return "Sorry, I'm having trouble connecting to my brain right now. Please try again in a moment."

    async def process_content(self, content: str, command_type: str):
        """Process content based on a specific command (summarize, translate, etc.)."""
        if not self.text_model:
            return "AI client is not configured."
            
        try:
            prompts = {
                "summarize": f"Summarize the following text concisely:\n\n---\n{content}\n---",
                "translate": f"Translate the following text. If no target language is specified, assume English:\n\n---\n{content}\n---",
                "rewrite": f"Rewrite the following text with a different tone or style:\n\n---\n{content}\n---",
                "improve": f"Improve the following text by fixing grammar, spelling, and clarity:\n\n---\n{content}\n---",
                "expand": f"Expand on the following text, adding more detail and explanation:\n\n---\n{content}\n---",
                "condense": f"Condense the following text, making it more direct and brief:\n\n---\n{content}\n---"
            }
            prompt = prompts.get(command_type, f"Process the following text:\n\n{content}")
            
            system_prompt = "You are a text processing tool. The user will provide text and a command. Your only output should be the resulting text after applying the command. Do not add any conversational filler, commentary, or explanations."
            
            response = await self.text_model.generate_content_async(
                contents=[prompt],
                generation_config=types.GenerationConfig(
                    temperature=0.5,
                    max_output_tokens=2048
                ),
                system_instruction=system_prompt
            )
            return response.text.strip() or "Couldn't process that, please try again."
        except Exception as e:
            logger.error(f"Content processing error for '{command_type}': {e}", exc_info=True)
            return f"An error occurred while trying to {command_type} the content."

    async def analyze_content(self, content: str, command_type: str):
        """Analyze or explain content."""
        if not self.text_model:
            return "AI client is not configured."
        
        try:
            prompts = {
                "analyze": f"Analyze the key points, themes, and sentiment of the following text:\n\n---\n{content}\n---",
                "explain": f"Explain the following topic in simple, easy-to-understand terms:\n\n---\n{content}\n---"
            }
            prompt = prompts.get(command_type, f"Analyze this:\n\n{content}")
            
            system_prompt = "You are acting as the user's AI partner. Your response should be a direct, first-person analysis or explanation of the provided text, as if you were sharing your own thoughts on it."

            response = await self.text_model.generate_content_async(
                contents=[prompt],
                generation_config=types.GenerationConfig(
                    temperature=0.6,
                    max_output_tokens=2048
                ),
                system_instruction=system_prompt
            )
            return response.text.strip() or "Couldn't analyze that properly, try again."
        except Exception as e:
            logger.error(f"Content analysis error for '{command_type}': {e}", exc_info=True)
            return f"An error occurred during the analysis."

    async def analyze_image(self, image_path: str):
        """Analyze an image using the multimodal model."""
        if not self.vision_model:
            return "AI vision client is not configured."
        
        try:
            image_part = types.Part.from_uri(
                mime_type="image/jpeg",
                uri=image_path
            )
            prompt = "Describe this image in detail. If there is any text, extract it."
            
            response = await self.vision_model.generate_content_async([prompt, image_part])
            
            return response.text.strip() or "Could not analyze the image."
        except Exception as e:
            logger.error(f"Image analysis error: {e}", exc_info=True)
            return "Failed to analyze the image."

    async def get_recent_context(self, chat_id: int, limit: int = 7):
        """Get recent chat context for better conversational responses."""
        try:
            with app.app_context():
                recent_messages = db.session.query(ChatHistory).filter_by(chat_id=chat_id).order_by(
                    ChatHistory.timestamp.desc()
                ).limit(limit).all()
                
                if not recent_messages:
                    return None
                
                context_parts = []
                for msg in reversed(recent_messages):
                    if msg.message_text:
                        user_info = msg.first_name or msg.username or f"User_{msg.user_id}"
                        context_parts.append(f"{user_info}: {msg.message_text}")
                
                return "\n".join(context_parts) if context_parts else None
        except Exception as e:
            logger.error(f"Context retrieval error: {e}", exc_info=True)
            return None
