"""Action Logger and History System
===================================

Tracks all automation actions for debugging and analysis.
"""

import logging
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime
import json

logger = logging.getLogger(__name__)


@dataclass
class ActionRecord:
    """Record of a single automation action."""
    action_type: str  # click, type, key, wait, screenshot, etc.
    timestamp: datetime = field(default_factory=datetime.now)
    target: Optional[str] = None  # element, coordinates, etc.
    value: Optional[str] = None  # text typed, key pressed, etc.
    screen_state: Optional[str] = None  # screen type at time of action
    success: bool = True
    error: Optional[str] = None
    duration_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "action_type": self.action_type,
            "timestamp": self.timestamp.isoformat(),
            "target": self.target,
            "value": self.value,
            "screen_state": self.screen_state,
            "success": self.success,
            "error": self.error,
            "duration_ms": self.duration_ms,
            "metadata": self.metadata,
        }


class ActionLogger:
    """Logs and tracks all automation actions."""
    
    def __init__(self, max_history: int = 1000):
        """Initialize action logger.
        
        Args:
            max_history: Maximum actions to keep in memory
        """
        self.max_history = max_history
        self.history: List[ActionRecord] = []
        logger.info("ActionLogger initialized")
    
    def log_action(
        self,
        action_type: str,
        target: Optional[str] = None,
        value: Optional[str] = None,
        screen_state: Optional[str] = None,
        success: bool = True,
        error: Optional[str] = None,
        duration_ms: float = 0.0,
        **metadata
    ) -> ActionRecord:
        """Log an action.
        
        Args:
            action_type: Type of action (click, type, key, etc.)
            target: Target of action (element, coordinates, etc.)
            value: Value associated with action
            screen_state: Screen state when action occurred
            success: Whether action was successful
            error: Error message if failed
            duration_ms: Duration of action in milliseconds
            **metadata: Additional metadata
            
        Returns:
            ActionRecord created
        """
        record = ActionRecord(
            action_type=action_type,
            target=target,
            value=value,
            screen_state=screen_state,
            success=success,
            error=error,
            duration_ms=duration_ms,
            metadata=metadata,
        )
        
        self.history.append(record)
        
        # Keep history size bounded
        if len(self.history) > self.max_history:
            self.history.pop(0)
        
        # Log
        level = logging.DEBUG if success else logging.WARNING
        msg = f"Action: {action_type}"
        if target:
            msg += f" on {target}"
        if value:
            msg += f" with value '{value}'"
        if not success:
            msg += f" - ERROR: {error}"
        
        logger.log(level, msg)
        
        return record
    
    def log_click(
        self,
        target: str,
        x: int,
        y: int,
        success: bool = True,
        error: Optional[str] = None,
        **metadata
    ) -> ActionRecord:
        """Log a click action."""
        return self.log_action(
            action_type="click",
            target=target,
            value=f"({x}, {y})",
            success=success,
            error=error,
            coordinates={"x": x, "y": y},
            **metadata
        )
    
    def log_type(
        self,
        value: str,
        success: bool = True,
        error: Optional[str] = None,
        **metadata
    ) -> ActionRecord:
        """Log a text typing action."""
        return self.log_action(
            action_type="type",
            value=value,
            success=success,
            error=error,
            **metadata
        )
    
    def log_key(
        self,
        key: str,
        success: bool = True,
        error: Optional[str] = None,
        **metadata
    ) -> ActionRecord:
        """Log a key press action."""
        return self.log_action(
            action_type="key",
            value=key,
            success=success,
            error=error,
            **metadata
        )
    
    def get_history(self, limit: Optional[int] = None) -> List[ActionRecord]:
        """Get action history.
        
        Args:
            limit: Maximum number of records to return
            
        Returns:
            List of action records
        """
        if limit:
            return self.history[-limit:]
        return self.history.copy()
    
    def get_last_action(self) -> Optional[ActionRecord]:
        """Get the last action."""
        return self.history[-1] if self.history else None
    
    def get_actions_by_type(self, action_type: str) -> List[ActionRecord]:
        """Get all actions of a specific type."""
        return [a for a in self.history if a.action_type == action_type]
    
    def get_failed_actions(self) -> List[ActionRecord]:
        """Get all failed actions."""
        return [a for a in self.history if not a.success]
    
    def get_summary(self) -> Dict[str, Any]:
        """Get summary statistics."""
        total = len(self.history)
        failed = len(self.get_failed_actions())
        
        action_counts = {}
        for record in self.history:
            action_counts[record.action_type] = \
                action_counts.get(record.action_type, 0) + 1
        
        return {
            "total_actions": total,
            "failed_actions": failed,
            "success_rate": (total - failed) / total if total > 0 else 1.0,
            "action_counts": action_counts,
        }
    
    def clear_history(self):
        """Clear all action history."""
        self.history.clear()
        logger.info("Action history cleared")
    
    def export_json(self) -> str:
        """Export history as JSON."""
        return json.dumps(
            [record.to_dict() for record in self.history],
            indent=2
        )
    
    def export_csv(self) -> str:
        """Export history as CSV."""
        if not self.history:
            return ""
        
        lines = [
            "action_type,timestamp,target,value,screen_state,success,error"
        ]
        
        for record in self.history:
            lines.append(
                f"{record.action_type},"
                f"{record.timestamp.isoformat()},"
                f'"{record.target or ""}'
                f'"{record.value or ""}'
                f'"{record.screen_state or ""}'
                f'{record.success},'
                f'"{record.error or ""}"'
            )
        
        return "\n".join(lines)
