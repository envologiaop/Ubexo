# Envo Telegram AI Userbot

## Overview

Envo is an advanced AI-powered Telegram userbot that integrates Google's Gemini AI model to provide intelligent conversational capabilities within Telegram chats. The system combines a Flask web dashboard with a Pyrogram-based Telegram client, featuring real-time information retrieval, voice transcription, and context-aware AI responses.

## System Architecture

### Backend Architecture
- **Flask Application**: Web server providing dashboard and health check endpoints
- **Pyrogram Client**: Telegram userbot implementation for message handling with session string authentication
- **SQLAlchemy ORM**: Database abstraction layer designed for PostgreSQL backend
- **Google Gemini AI**: Primary AI model (gemini-2.5-flash) for text generation and understanding
- **Asynchronous Processing**: Event-driven message handling with async/await patterns

### Frontend Architecture
- **Bootstrap 5**: Dark theme responsive web interface
- **Real-time Status**: JavaScript-based status monitoring via AJAX calls
- **Single Page Application**: Dashboard showing userbot status and features

## Key Components

### Core Application (`app.py`)
- Flask web server with ProxyFix middleware for deployment environments
- Database configuration with connection pooling and health checks
- Environment-based configuration management with fallback defaults
- Health check endpoint for monitoring service status

### Telegram Userbot (`userbot.py`)
- Pyrogram client with session string authentication
- Command handlers for user interactions (`.ask`, `.summarize`)
- Message processing pipeline with context awareness
- Queue system for rate limiting and command management
- Background thread management for concurrent operations

### AI Integration (`gemini_client.py`)
- Google Gemini 2.5 Flash model integration with API key authentication
- Context-aware response generation with conversation history
- Real-time information retrieval using DuckDuckGo API
- Structured prompt engineering with personality traits
- Automatic detection of queries requiring current information

### Data Models (`models.py`)
- **ChatHistory**: Complete message storage with metadata (chat_id, user info, timestamps)
- **UserContext**: User-specific preferences and roleplay contexts
- **CommandQueue**: Rate limiting and command processing queue with status tracking

### Utility Functions (`utils.py`)
- Voice message transcription using speech_recognition library
- Image analysis capabilities (partially implemented)
- Context retrieval functions for conversation history
- Error message formatting utilities

## Data Flow

1. **Message Reception**: Pyrogram client receives Telegram messages
2. **Command Processing**: Message filters identify user commands (`.ask`, `.summarize`)
3. **Context Retrieval**: System fetches relevant chat history and user context
4. **AI Processing**: Gemini client processes query with context and web search if needed
5. **Response Generation**: AI generates contextually appropriate response
6. **Message Storage**: All interactions stored in PostgreSQL for future context
7. **Response Delivery**: Processed response sent back to Telegram chat

## External Dependencies

### APIs and Services
- **Google Gemini API**: Primary AI model for response generation
- **Telegram API**: Message handling via Pyrogram client
- **DuckDuckGo API**: Real-time information retrieval
- **Speech Recognition**: Google Speech API with Sphinx fallback

### Python Libraries
- **Flask & SQLAlchemy**: Web framework and ORM
- **Pyrogram**: Telegram client library
- **google-genai**: Google Gemini AI client
- **speech_recognition**: Voice transcription
- **requests**: HTTP client for web searches
- **Pillow**: Image processing

## Deployment Strategy

### Web Service Architecture (Updated June 30, 2025)
- **Flask Web Service**: Successfully converted from background service to web service
- **Health Check Endpoints**: `/health` and `/status` for monitoring
- **Web Dashboard**: Real-time status monitoring with deployment-ready interface
- **Standalone Userbot Service**: Separate service for Telegram functionality
- **PostgreSQL Database**: Managed database service for data persistence
- **Environment Variables**: Secure storage of API keys and session strings

### Required Environment Variables
- `GEMINI_API_KEY`: Google AI Studio API key ✓ Configured
- `TELEGRAM_SESSION_STRING`: Generated via Pyrogram for userbot authentication ✓ Configured
- `DATABASE_URL`: PostgreSQL connection string (auto-provided)
- `SESSION_SECRET`: Flask session security key

### Web Service Endpoints
- `/` - Main dashboard with deployment status and features
- `/health` - Health check endpoint (returns JSON status)
- `/status` - Detailed userbot status and credential verification
- `/start_userbot` - POST endpoint to initialize userbot on demand

### Database Schema
The application uses PostgreSQL with three main tables:
- Chat history for message storage and context retrieval
- User context for personalization and roleplay settings
- Command queue for rate limiting and processing management

## Changelog

```
Changelog:
- June 30, 2025. Initial setup
- June 30, 2025. Successfully converted from Render background service to web service architecture
- June 30, 2025. Added Flask web dashboard with health check endpoints and deployment status
- June 30, 2025. Configured PostgreSQL database and all required environment variables
- June 30, 2025. Web service now ready for deployment to any hosting platform
- June 30, 2025. Updated behavior to act like user personally, removed all AI branding and signatures, made responses natural and human-like
```

## User Preferences

```
Preferred communication style: Simple, everyday language.
```