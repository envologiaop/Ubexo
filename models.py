from app import db
from datetime import datetime
from sqlalchemy import Text, BigInteger

class ChatHistory(db.Model):
    """Store complete chat history for context retrieval"""
    id = db.Column(db.Integer, primary_key=True)
    chat_id = db.Column(BigInteger, nullable=False, index=True)
    message_id = db.Column(BigInteger, nullable=False)
    user_id = db.Column(BigInteger, nullable=True)
    username = db.Column(db.String(64), nullable=True)
    first_name = db.Column(db.String(64), nullable=True)
    last_name = db.Column(db.String(64), nullable=True)
    message_text = db.Column(Text, nullable=True)
    message_type = db.Column(db.String(32), nullable=False, default='text')  # text, photo, voice, video, document
    file_id = db.Column(db.String(256), nullable=True)
    reply_to_message_id = db.Column(BigInteger, nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    def __repr__(self):
        return f'<ChatHistory {self.chat_id}:{self.message_id}>'

class UserContext(db.Model):
    """Store user-specific context and preferences"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(BigInteger, unique=True, nullable=False)
    current_roleplay = db.Column(db.String(128), nullable=True)
    conversation_context = db.Column(Text, nullable=True)
    last_interaction = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<UserContext {self.user_id}>'

class CommandQueue(db.Model):
    """Queue system for rate limiting"""
    id = db.Column(db.Integer, primary_key=True)
    chat_id = db.Column(BigInteger, nullable=False)
    user_id = db.Column(BigInteger, nullable=False)
    command = db.Column(db.String(64), nullable=False)
    status = db.Column(db.String(32), default='pending')  # pending, processing, completed, failed
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    processed_at = db.Column(db.DateTime, nullable=True)
    
    def __repr__(self):
        return f'<CommandQueue {self.command} - {self.status}>'
