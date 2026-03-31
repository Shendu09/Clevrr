"""
Chat History & Conversation Memory System.

Stores multi-turn conversations for context-aware AI responses.
Integrates with existing MemorySystem for persistent storage.

Features:
- Multi-turn conversation tracking
- Context window management
- Conversation summarization
- Semantic search over past conversations
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, asdict
import logging

logger = logging.getLogger(__name__)


@dataclass
class Message:
    """Single message in conversation."""
    role: str  # 'user' or 'assistant'
    content: str
    timestamp: str
    metadata: Optional[Dict[str, Any]] = None  # Additional context


@dataclass
class Conversation:
    """Multi-turn conversation."""
    id: int
    conversation_id: str  # Unique ID for this conversation
    messages: List[Message]
    topic: Optional[str] = None
    created_at: str = None
    updated_at: str = None
    summary: Optional[str] = None
    success: Optional[bool] = None  # Did conversation achieve goal?


class ChatHistory:
    """Manage conversation history with multi-turn context."""
    
    def __init__(self, db_path: str = "data/memory.db", max_context_messages: int = 20):
        """
        Initialize chat history.
        
        Args:
            db_path: Path to SQLite database
            max_context_messages: Number of recent messages to include in context
        """
        self.db_path = db_path
        self.max_context_messages = max_context_messages
        self.current_conversation_id = None
        
        # Create database if needed
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._initialize_db()
    
    def _initialize_db(self):
        """Create chat history tables."""
        with self._connect() as conn:
            # Conversations table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id TEXT UNIQUE NOT NULL,
                    topic TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    summary TEXT,
                    success INTEGER,
                    message_count INTEGER DEFAULT 0
                )
            """)
            
            # Messages table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    metadata TEXT,
                    FOREIGN KEY (conversation_id) REFERENCES conversations(conversation_id)
                )
            """)
            
            # Create indices for faster queries
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_conversation_id 
                ON messages(conversation_id)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_timestamp 
                ON messages(timestamp)
            """)
            
            conn.commit()
            logger.info("[ChatHistory] Database initialized")
    
    def _connect(self):
        """Get database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def start_conversation(self, topic: Optional[str] = None) -> str:
        """
        Start new conversation.
        
        Args:
            topic: Optional topic/description
        
        Returns:
            Conversation ID
        """
        import uuid
        conversation_id = str(uuid.uuid4())
        now = datetime.now().isoformat()
        
        with self._connect() as conn:
            conn.execute("""
                INSERT INTO conversations 
                (conversation_id, topic, created_at, updated_at, message_count)
                VALUES (?, ?, ?, ?, 0)
            """, (conversation_id, topic, now, now))
            conn.commit()
        
        self.current_conversation_id = conversation_id
        logger.debug(f"[ChatHistory] Started conversation {conversation_id}")
        return conversation_id
    
    def add_user_message(self, content: str, metadata: Optional[Dict] = None) -> bool:
        """
        Add user message to current conversation.
        
        Args:
            content: Message text
            metadata: Optional metadata (action type, parameters, etc.)
        
        Returns:
            True if successful
        """
        if not self.current_conversation_id:
            self.start_conversation()
        
        return self._add_message(self.current_conversation_id, "user", content, metadata)
    
    def add_assistant_message(self, content: str, metadata: Optional[Dict] = None) -> bool:
        """
        Add assistant message to current conversation.
        
        Args:
            content: Message text
            metadata: Optional metadata (action taken, result, etc.)
        
        Returns:
            True if successful
        """
        if not self.current_conversation_id:
            self.start_conversation()
        
        return self._add_message(self.current_conversation_id, "assistant", content, metadata)
    
    def _add_message(self, conversation_id: str, role: str, content: str, 
                    metadata: Optional[Dict] = None) -> bool:
        """Add message to conversation."""
        try:
            timestamp = datetime.now().isoformat()
            metadata_json = json.dumps(metadata) if metadata else None
            
            with self._connect() as conn:
                conn.execute("""
                    INSERT INTO messages 
                    (conversation_id, role, content, timestamp, metadata)
                    VALUES (?, ?, ?, ?, ?)
                """, (conversation_id, role, content, timestamp, metadata_json))
                
                # Update conversation's updated_at and message_count
                conn.execute("""
                    UPDATE conversations 
                    SET updated_at = ?, message_count = message_count + 1
                    WHERE conversation_id = ?
                """, (timestamp, conversation_id))
                
                conn.commit()
            
            return True
        except Exception as e:
            logger.error(f"[ChatHistory] Failed to add message: {e}")
            return False
    
    def get_context_window(self, 
                          conversation_id: Optional[str] = None,
                          num_messages: Optional[int] = None,
                          include_metadata: bool = True) -> List[Dict[str, str]]:
        """
        Get recent messages for context.
        
        Args:
            conversation_id: Which conversation (default: current)
            num_messages: How many messages (default: max_context_messages)
            include_metadata: Include metadata dict
        
        Returns:
            List of messages in OpenAI format: [{"role": "user", "content": "..."}, ...]
        """
        if not conversation_id:
            conversation_id = self.current_conversation_id
        if not conversation_id:
            return []
        
        num_messages = num_messages or self.max_context_messages
        
        try:
            with self._connect() as conn:
                rows = conn.execute("""
                    SELECT role, content, metadata
                    FROM messages
                    WHERE conversation_id = ?
                    ORDER BY timestamp DESC
                    LIMIT ?
                """, (conversation_id, num_messages)).fetchall()
            
            # Reverse to chronological order
            messages = []
            for row in reversed(rows):
                msg = {
                    "role": row[0],
                    "content": row[1]
                }
                
                if include_metadata and row[2]:
                    try:
                        msg["metadata"] = json.loads(row[2])
                    except:
                        pass
                
                messages.append(msg)
            
            return messages
        except Exception as e:
            logger.error(f"[ChatHistory] Failed to get context: {e}")
            return []
    
    def get_conversation_history(self, 
                                conversation_id: Optional[str] = None) -> Optional[Conversation]:
        """
        Get full conversation.
        
        Args:
            conversation_id: Which conversation (default: current)
        
        Returns:
            Conversation object or None
        """
        if not conversation_id:
            conversation_id = self.current_conversation_id
        if not conversation_id:
            return None
        
        try:
            with self._connect() as conn:
                # Get conversation metadata
                conv_row = conn.execute("""
                    SELECT id, conversation_id, topic, created_at, updated_at, summary, success
                    FROM conversations
                    WHERE conversation_id = ?
                """, (conversation_id,)).fetchone()
                
                if not conv_row:
                    return None
                
                # Get all messages
                msg_rows = conn.execute("""
                    SELECT role, content, timestamp, metadata
                    FROM messages
                    WHERE conversation_id = ?
                    ORDER BY timestamp ASC
                """, (conversation_id,)).fetchall()
                
                messages = [
                    Message(
                        role=row[0],
                        content=row[1],
                        timestamp=row[2],
                        metadata=json.loads(row[3]) if row[3] else None
                    )
                    for row in msg_rows
                ]
                
                return Conversation(
                    id=conv_row[0],
                    conversation_id=conv_row[1],
                    messages=messages,
                    topic=conv_row[2],
                    created_at=conv_row[3],
                    updated_at=conv_row[4],
                    summary=conv_row[5],
                    success=conv_row[6]
                )
        
        except Exception as e:
            logger.error(f"[ChatHistory] Failed to get conversation: {e}")
            return None
    
    def end_conversation(self, summary: Optional[str] = None, success: Optional[bool] = None):
        """
        End current conversation.
        
        Args:
            summary: Summary of what happened
            success: Whether goal was achieved
        """
        if not self.current_conversation_id:
            return
        
        try:
            with self._connect() as conn:
                conn.execute("""
                    UPDATE conversations
                    SET summary = ?, success = ?
                    WHERE conversation_id = ?
                """, (summary, success, self.current_conversation_id))
                conn.commit()
            
            logger.debug(f"[ChatHistory] Ended conversation {self.current_conversation_id}")
            self.current_conversation_id = None
        
        except Exception as e:
            logger.error(f"[ChatHistory] Failed to end conversation: {e}")
    
    def search_conversations(self, query: str, limit: int = 10) -> List[Conversation]:
        """
        Search past conversations by topic or summary.
        
        Args:
            query: Search query
            limit: Max results
        
        Returns:
            List of matching conversations
        """
        try:
            with self._connect() as conn:
                rows = conn.execute("""
                    SELECT conversation_id, topic, summary
                    FROM conversations
                    WHERE topic LIKE ? OR summary LIKE ?
                    ORDER BY updated_at DESC
                    LIMIT ?
                """, (f"%{query}%", f"%{query}%", limit)).fetchall()
                
                conversations = [
                    self.get_conversation_history(row[0])
                    for row in rows
                ]
                return [c for c in conversations if c]
        
        except Exception as e:
            logger.error(f"[ChatHistory] Search failed: {e}")
            return []
    
    def get_recent_conversations(self, limit: int = 10) -> List[Conversation]:
        """Get recently updated conversations."""
        try:
            with self._connect() as conn:
                rows = conn.execute("""
                    SELECT conversation_id
                    FROM conversations
                    ORDER BY updated_at DESC
                    LIMIT ?
                """, (limit,)).fetchall()
                
                conversations = [
                    self.get_conversation_history(row[0])
                    for row in rows
                ]
                return [c for c in conversations if c]
        
        except Exception as e:
            logger.error(f"[ChatHistory] Failed to get recent: {e}")
            return []
    
    def clear_old_conversations(self, days: int = 30):
        """Delete conversations older than N days."""
        try:
            from datetime import datetime, timedelta
            cutoff = (datetime.now() - timedelta(days=days)).isoformat()
            
            with self._connect() as conn:
                # Get conversation_ids to delete
                rows = conn.execute("""
                    SELECT conversation_id FROM conversations WHERE updated_at < ?
                """, (cutoff,)).fetchall()
                
                for row in rows:
                    conv_id = row[0]
                    # Delete messages
                    conn.execute("DELETE FROM messages WHERE conversation_id = ?", (conv_id,))
                    # Delete conversation
                    conn.execute("DELETE FROM conversations WHERE conversation_id = ?", (conv_id,))
                
                conn.commit()
                logger.info(f"[ChatHistory] Cleared {len(rows)} conversations older than {days} days")
        
        except Exception as e:
            logger.error(f"[ChatHistory] Cleanup failed: {e}")


# Global chat history instance
_chat_history: Optional[ChatHistory] = None


def initialize_chat_history(db_path: str = "data/memory.db") -> ChatHistory:
    """Initialize global chat history."""
    global _chat_history
    _chat_history = ChatHistory(db_path=db_path)
    return _chat_history


def get_chat_history() -> ChatHistory:
    """Get global chat history instance."""
    global _chat_history
    if _chat_history is None:
        _chat_history = ChatHistory()
    return _chat_history


def start_conversation(topic: Optional[str] = None) -> str:
    """Start new conversation."""
    return get_chat_history().start_conversation(topic)


def add_user_message(content: str, metadata: Optional[Dict] = None) -> bool:
    """Add user message."""
    return get_chat_history().add_user_message(content, metadata)


def add_assistant_message(content: str, metadata: Optional[Dict] = None) -> bool:
    """Add assistant message."""
    return get_chat_history().add_assistant_message(content, metadata)


def get_context_window(num_messages: Optional[int] = None) -> List[Dict[str, str]]:
    """Get conversation context for LLM."""
    return get_chat_history().get_context_window(num_messages=num_messages)
