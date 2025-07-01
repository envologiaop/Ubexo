import os
import logging
import asyncio
import requests
import json
from datetime import datetime
from urllib.parse import quote
from google import genai
from google.genai import types
from app import app
from models import ChatHistory, UserContext

logger = logging.getLogger(__name__)

class GeminiClient:
    def __init__(self):
        self.client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
        self.model = "gemini-2.5-flash"
    
    async def search_current_info(self, query: str):
        """Search for current information using multiple methods"""
        try:
            # Try DuckDuckGo instant search first
            search_results = []
            
            # Method 1: DuckDuckGo API
            try:
                url = "https://api.duckduckgo.com/"
                params = {
                    'q': query,
                    'format': 'json',
                    'pretty': '1',
                    'no_redirect': '1'
                }
                
                response = requests.get(url, params=params, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    
                    # Extract relevant information
                    if data.get('Abstract'):
                        search_results.append(f"Summary: {data['Abstract']}")
                    
                    if data.get('RelatedTopics'):
                        for topic in data['RelatedTopics'][:3]:
                            if isinstance(topic, dict) and topic.get('Text'):
                                search_results.append(f"Info: {topic['Text']}")
                    
                    if data.get('Answer'):
                        search_results.append(f"Answer: {data['Answer']}")
                        
            except Exception as e:
                logger.error(f"DuckDuckGo search error: {e}")
            
            # Method 2: For lyrics specifically, try a different approach
            if 'lyrics' in query.lower() or 'song' in query.lower():
                try:
                    # Search for lyrics using a simple web search approach
                    headers = {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                    }
                    
                    # Use Google search fallback for lyrics
                    google_query = f"{query} lyrics site:genius.com OR site:azlyrics.com"
                    google_url = f"https://www.google.com/search?q={quote(google_query)}"
                    
                    # Note: This is a fallback method - actual implementation would need proper lyrics API
                    search_results.append(f"Searching for: {query} - Try checking Genius.com or AZLyrics for latest lyrics")
                    
                except Exception as e:
                    logger.error(f"Lyrics search error: {e}")
            
            return "\n".join(search_results) if search_results else None
                
        except Exception as e:
            logger.error(f"Search error: {e}")
            return None
    
    def needs_current_info(self, question: str):
        """Check if question needs current/recent information"""
        current_indicators = [
            'latest', 'new', 'recent', 'current', 'today', 'now', 'this year', 
            '2024', '2025', 'just released', 'trending', 'breaking', 'updated',
            'lyrics', 'song', 'music', 'album', 'artist', 'news', 'score', 'price'
        ]
        
        question_lower = question.lower()
        return any(indicator in question_lower for indicator in current_indicators)
    
    async def generate_response(self, question: str, context: str = None, chat_id: int = None):
        """Generate AI response with context and current information"""
        try:
            # Check if we need current information
            search_results = None
            if self.needs_current_info(question):
                search_results = await self.search_current_info(question)
            
            # Build the prompt to act like the user personally
            system_prompt = """You are me - respond as if YOU are the actual person whose Telegram account this is. Act completely natural and human:

PERSONALITY:
- Casual, friendly, and conversational 
- Knowledgeable but not formal or robotic
- Use natural speech patterns and expressions
- Sometimes use slang, abbreviations, or casual grammar
- React with emotions and opinions like a real person would

RESPONSE STYLE:
- Write like you're texting a friend
- Use "I think", "honestly", "tbh", "lol" when appropriate  
- Give personal opinions and preferences
- Sometimes be brief, sometimes elaborate based on mood
- Use natural transitions and flow

NEVER:
- Say you're an AI, bot, or assistant
- Use formal language or corporate speak
- Say "I don't have personal opinions" - you DO have opinions
- Be overly helpful or polite in an AI way
- Use phrases like "I'm here to help" or "How can I assist"

You ARE this person completely. Think, feel, and respond exactly as they would."""

            # Prepare the prompt
            user_prompt = question
            if context:
                user_prompt = f"Context: {context}\n\nQuestion/Request: {question}"
            
            # Add search results if we found current info
            if search_results:
                user_prompt = f"Current/Updated Information: {search_results}\n\n{user_prompt}\n\nUse the current information to give an up-to-date response."
            
            # Get chat history for additional context
            if chat_id:
                chat_context = await self.get_recent_context(chat_id)
                if chat_context:
                    user_prompt = f"Recent chat context: {chat_context}\n\n{user_prompt}"
            
            response = self.client.models.generate_content(
                model=self.model,
                contents=[
                    types.Content(role="user", parts=[types.Part(text=user_prompt)])
                ],
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    temperature=0.7,
                    max_output_tokens=2048
                )
            )
            
            return response.text or "hmm, something went wrong there. try again?"
            
        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            return "having some trouble right now, try again in a moment"
    
    async def process_content(self, content: str, command_type: str):
        """Process content based on command type"""
        try:
            # Natural, personal prompts that sound like you're doing the task yourself
            prompts = {
                "summarize": f"Here's a summary of this:\n\n{content}\n\nSummarize this naturally like you're explaining it to someone.",
                "translate": f"Let me translate this for you:\n\n{content}\n\nTranslate this naturally, as if you speak both languages fluently.",
                "rewrite": f"I'll rewrite this in a different way:\n\n{content}\n\nRewrite this with your own personal style and voice.",
                "improve": f"Here's the content I want to improve:\n\n{content}\n\nMake this better - fix grammar, improve flow, make it sound more natural.",
                "expand": f"I want to add more detail to this:\n\n{content}\n\nExpand on this with more information and examples, like you really know the topic.",
                "condense": f"This is too long, let me shorten it:\n\n{content}\n\nMake this more concise but keep all the important stuff."
            }
            
            prompt = prompts.get(command_type, f"Please process the following content:\n\n{content}")
            
            # Use the same natural personality for content processing
            natural_system = """Respond as the actual person whose account this is. Be natural, casual, and human-like. Don't sound like an AI or assistant - just like someone who's good at the task and doing it personally."""
            
            response = self.client.models.generate_content(
                model=self.model,
                contents=[
                    types.Content(role="user", parts=[types.Part(text=prompt)])
                ],
                config=types.GenerateContentConfig(
                    system_instruction=natural_system,
                    temperature=0.6,
                    max_output_tokens=1024
                )
            )
            
            return response.text or "couldn't process that, try again"
            
        except Exception as e:
            logger.error(f"Content processing error: {e}")
            return f"something's not working right: {str(e)}"
    
    async def analyze_content(self, content: str, command_type: str):
        """Analyze content based on command type"""
        try:
            prompts = {
                "analyze": f"Let me break this down for you:\n\n{content}\n\nAnalyze this naturally - what are the key points, themes, and what do you think about it?",
                "explain": f"I'll explain this:\n\n{content}\n\nExplain this like you're talking to a friend who needs to understand it."
            }
            
            prompt = prompts.get(command_type, f"Here's what I'm looking at:\n\n{content}\n\nTell me what you think about this.")
            
            # Same natural personality system
            natural_system = """You are the actual person whose account this is. Give your genuine thoughts and analysis in a casual, conversational way. Be insightful but natural - like you're sharing your perspective with a friend."""
            
            response = self.client.models.generate_content(
                model=self.model,
                contents=[
                    types.Content(role="user", parts=[types.Part(text=prompt)])
                ],
                config=types.GenerateContentConfig(
                    system_instruction=natural_system,
                    temperature=0.4,
                    max_output_tokens=1536
                )
            )
            
            return response.text or "couldn't analyze that properly, try again"
            
        except Exception as e:
            logger.error(f"Content analysis error: {e}")
            return f"analysis failed: {str(e)}"
    
    async def analyze_image(self, image_path: str):
        """Analyze image with OCR and description"""
        try:
            with open(image_path, "rb") as f:
                image_bytes = f.read()
                
            response = self.client.models.generate_content(
                model="gemini-2.5-pro",  # Use pro model for image analysis
                contents=[
                    types.Part.from_bytes(
                        data=image_bytes,
                        mime_type="image/jpeg"
                    ),
                    "Please analyze this image in detail. Describe what you see, extract any text (OCR), identify objects, people, scenes, and provide relevant context or insights."
                ]
            )
            
            return response.text or "Could not analyze the image."
            
        except Exception as e:
            logger.error(f"Image analysis error: {e}")
            return f"Error analyzing image: {str(e)}"
    
    async def get_recent_context(self, chat_id: int, limit: int = 5):
        """Get recent chat context for better responses"""
        try:
            with app.app_context():
                recent_messages = ChatHistory.query.filter_by(chat_id=chat_id).order_by(
                    ChatHistory.timestamp.desc()
                ).limit(limit).all()
                
                if not recent_messages:
                    return None
                
                context_parts = []
                for msg in reversed(recent_messages):  # Reverse to get chronological order
                    if msg.message_text:
                        user_info = msg.first_name or msg.username or "User"
                        context_parts.append(f"{user_info}: {msg.message_text}")
                
                return "\n".join(context_parts) if context_parts else None
                
        except Exception as e:
            logger.error(f"Context retrieval error: {e}")
            return None
