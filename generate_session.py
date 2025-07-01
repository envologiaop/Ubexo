#!/usr/bin/env python3
"""
Telegram Session String Generator for Envo Userbot
Run this script locally to generate your session string for deployment.
"""

from pyrogram import Client
import os

def generate_session():
    print("🔑 Telegram Session String Generator for Envo")
    print("=" * 50)
    
    # Get API credentials
    api_id = input("Enter your API ID: ").strip()
    api_hash = input("Enter your API Hash: ").strip()
    
    if not api_id or not api_hash:
        print("❌ Error: API ID and Hash are required!")
        return
    
    try:
        # Convert API ID to integer
        api_id = int(api_id)
        
        print("\n📱 Creating Telegram session...")
        print("You'll need to enter your phone number and verification code.")
        
        # Create client and generate session string
        with Client("envo_session", api_id, api_hash) as app:
            session_string = app.export_session_string()
            
            print("\n✅ Session generated successfully!")
            print("\n🔐 Your Session String:")
            print("-" * 50)
            print(session_string)
            print("-" * 50)
            
            print("\n📋 Next Steps:")
            print("1. Copy the session string above")
            print("2. Add it to your Render environment variables as 'TELEGRAM_SESSION_STRING'")
            print("3. Never share this session string with anyone!")
            
            # Save to file for convenience
            with open("session_string.txt", "w") as f:
                f.write(session_string)
            
            print(f"\n💾 Session string also saved to: session_string.txt")
            print("⚠️  Remember to delete this file after deployment!")
            
    except ValueError:
        print("❌ Error: API ID must be a number")
    except Exception as e:
        print(f"❌ Error: {e}")
        print("\nTroubleshooting:")
        print("- Make sure your API ID and Hash are correct")
        print("- Check your internet connection")
        print("- Verify your phone number is correct")

if __name__ == "__main__":
    generate_session()
