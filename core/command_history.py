"""
Command History UI Panel — Display recent commands in overlay.

Shows:
- Last 10 commands
- Success/failure status
- Execution time
- Clickable to re-run
- Search functionality

Integrated into Electron overlay.
"""

# This is a supporting module for the command history panel
# The actual UI is built in HTML/JavaScript but this Python module
# manages the history data and display state

import json
import sqlite3
from datetime import datetime
from typing import List, Dict, Optional
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class CommandHistory:
    """Manage command history for UI display."""
    
    def __init__(self, db_path: str = "data/memory.db", max_history: int = 100):
        """
        Initialize command history.
        
        Args:
            db_path: Path to SQLite database
            max_history: Maximum commands to store
        """
        self.db_path = db_path
        self.max_history = max_history
        
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._initialize_db()
    
    def _initialize_db(self):
        """Create command history table."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS command_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    command TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    status TEXT DEFAULT 'pending',
                    result TEXT,
                    duration_ms INTEGER,
                    success INTEGER DEFAULT 0,
                    error_message TEXT
                )
            """)
            
            # Create index for faster queries
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_timestamp 
                ON command_history(timestamp DESC)
            """)
            
            conn.commit()
            logger.info("[CommandHistory] Database initialized")
    
    def add_command(self, command: str, status: str = "pending") -> int:
        """
        Add command to history.
        
        Args:
            command: Command text
            status: 'pending', 'executing', 'success', 'failed'
        
        Returns:
            Command ID
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    INSERT INTO command_history 
                    (command, timestamp, status)
                    VALUES (?, ?, ?)
                """, (command, datetime.now().isoformat(), status))
                conn.commit()
                
                cmd_id = cursor.lastrowid
                logger.debug(f"[CommandHistory] Added command {cmd_id}: {command}")
                return cmd_id
        
        except Exception as e:
            logger.error(f"[CommandHistory] Failed to add command: {e}")
            return None
    
    def update_command(self, cmd_id: int, status: str, 
                      result: Optional[str] = None,
                      duration_ms: Optional[int] = None,
                      success: bool = False,
                      error_message: Optional[str] = None):
        """
        Update command status after execution.
        
        Args:
            cmd_id: Command ID
            status: Result status
            result: Result description
            duration_ms: Execution time in milliseconds
            success: Whether successful
            error_message: Error if failed
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    UPDATE command_history
                    SET status = ?, result = ?, duration_ms = ?, 
                        success = ?, error_message = ?
                    WHERE id = ?
                """, (status, result, duration_ms, success, error_message, cmd_id))
                conn.commit()
            
            logger.debug(f"[CommandHistory] Updated command {cmd_id}: {status}")
        
        except Exception as e:
            logger.error(f"[CommandHistory] Failed to update command: {e}")
    
    def get_recent(self, limit: int = 10) -> List[Dict]:
        """
        Get recent commands.
        
        Args:
            limit: Number of commands to return
        
        Returns:
            List of command dicts
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute("""
                    SELECT id, command, timestamp, status, result, 
                           duration_ms, success, error_message
                    FROM command_history
                    ORDER BY timestamp DESC
                    LIMIT ?
                """, (limit,)).fetchall()
                
                return [
                    {
                        "id": row[0],
                        "command": row[1],
                        "timestamp": row[2],
                        "status": row[3],
                        "result": row[4],
                        "duration_ms": row[5],
                        "success": bool(row[6]),
                        "error_message": row[7]
                    }
                    for row in rows
                ]
        
        except Exception as e:
            logger.error(f"[CommandHistory] Failed to get recent: {e}")
            return []
    
    def search(self, query: str, limit: int = 20) -> List[Dict]:
        """
        Search command history.
        
        Args:
            query: Search query
            limit: Max results
        
        Returns:
            List of matching commands
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute("""
                    SELECT id, command, timestamp, status, result, 
                           duration_ms, success, error_message
                    FROM command_history
                    WHERE command LIKE ?
                    ORDER BY timestamp DESC
                    LIMIT ?
                """, (f"%{query}%", limit)).fetchall()
                
                return [
                    {
                        "id": row[0],
                        "command": row[1],
                        "timestamp": row[2],
                        "status": row[3],
                        "result": row[4],
                        "duration_ms": row[5],
                        "success": bool(row[6]),
                        "error_message": row[7]
                    }
                    for row in rows
                ]
        
        except Exception as e:
            logger.error(f"[CommandHistory] Failed to search: {e}")
            return []
    
    def get_stats(self) -> Dict:
        """
        Get command history statistics.
        
        Returns:
            Stats dict with totals, success rate, etc.
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                total = conn.execute(
                    "SELECT COUNT(*) FROM command_history"
                ).fetchone()[0]
                
                successful = conn.execute(
                    "SELECT COUNT(*) FROM command_history WHERE success = 1"
                ).fetchone()[0]
                
                failed = conn.execute(
                    "SELECT COUNT(*) FROM command_history WHERE success = 0 AND status = 'failed'"
                ).fetchone()[0]
                
                avg_duration = conn.execute(
                    "SELECT AVG(duration_ms) FROM command_history WHERE duration_ms IS NOT NULL"
                ).fetchone()[0]
                
                return {
                    "total": total,
                    "successful": successful,
                    "failed": failed,
                    "success_rate": (successful / total * 100) if total > 0 else 0,
                    "avg_duration_ms": round(avg_duration) if avg_duration else 0
                }
        
        except Exception as e:
            logger.error(f"[CommandHistory] Failed to get stats: {e}")
            return {}
    
    def clear(self):
        """Clear all history."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("DELETE FROM command_history")
                conn.commit()
            
            logger.info("[CommandHistory] Cleared all history")
        
        except Exception as e:
            logger.error(f"[CommandHistory] Failed to clear: {e}")
    
    def export(self, format: str = "json") -> Optional[str]:
        """
        Export history.
        
        Args:
            format: 'json' or 'csv'
        
        Returns:
            Exported data as string
        """
        try:
            commands = self.get_recent(limit=self.max_history)
            
            if format == "json":
                return json.dumps(commands, indent=2)
            
            elif format == "csv":
                import csv
                from io import StringIO
                
                output = StringIO()
                writer = csv.DictWriter(
                    output,
                    fieldnames=["id", "command", "timestamp", "status", "duration_ms", "success"]
                )
                writer.writeheader()
                writer.writerows(commands)
                return output.getvalue()
        
        except Exception as e:
            logger.error(f"[CommandHistory] Failed to export: {e}")
            return None


# Global history instance
_history: Optional[CommandHistory] = None


def initialize_command_history(db_path: str = "data/memory.db") -> CommandHistory:
    """Initialize global command history."""
    global _history
    _history = CommandHistory(db_path=db_path)
    return _history


def get_command_history() -> CommandHistory:
    """Get global command history."""
    global _history
    if _history is None:
        _history = CommandHistory()
    return _history


def add_command(command: str) -> int:
    """Add command to history."""
    return get_command_history().add_command(command)


def update_command(cmd_id: int, status: str, result: Optional[str] = None, 
                  duration_ms: Optional[int] = None, success: bool = False):
    """Update command result."""
    return get_command_history().update_command(cmd_id, status, result, duration_ms, success)


def get_recent_commands(limit: int = 10) -> List[Dict]:
    """Get recent commands."""
    return get_command_history().get_recent(limit)


def search_commands(query: str) -> List[Dict]:
    """Search command history."""
    return get_command_history().search(query)


def get_command_stats() -> Dict:
    """Get command statistics."""
    return get_command_history().get_stats()
