#!/usr/bin/env python3
"""
Standalone Userbot Service for Envo
This runs the Telegram userbot as a separate service from the Flask web app.
"""

import os
import sys
import asyncio
import logging
from pathlib import Path

# Ensure we're working in the correct directory
os.chdir(Path(__file__).parent)

try:
    from userbot import UserbotManager
except ImportError:
    # Add current directory to path if import fails
    sys.path.insert(0, str(Path(__file__).parent))
    from userbot import UserbotManager

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def main():
    """Main function to run the userbot service"""
    
    # Check for required environment variables
    session_string = os.environ.get("TELEGRAM_SESSION_STRING")
    gemini_key = os.environ.get("GEMINI_API_KEY")
    
    if not session_string:
        logger.error("TELEGRAM_SESSION_STRING environment variable is required")
        sys.exit(1)
    
    if not gemini_key:
        logger.error("GEMINI_API_KEY environment variable is required")
        sys.exit(1)
    
    logger.info("Starting Envo Telegram Userbot Service...")
    
    try:
        # Initialize and start the userbot
        userbot_manager = UserbotManager()
        await userbot_manager.start()
        
    except KeyboardInterrupt:
        logger.info("Userbot service stopped by user")
    except Exception as e:
        logger.error(f"Userbot service error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    # Run the userbot service
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Service interrupted")
    except Exception as e:
        logger.error(f"Service failed: {e}")
        sys.exit(1)