"""Real-time Dashboard for Event Loop Monitoring

Provides real-time visibility into event loop state, tasks, and metrics.
Inspired by CLOVIS-style system monitoring.
"""

import asyncio
from typing import Dict, Any, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import json


class DashboardUpdateType(Enum):
    """Types of dashboard updates."""
    LOOP_STATE_CHANGE = "loop_state_change"
    TASK_STARTED = "task_started"
    TASK_COMPLETED = "task_completed"
    ACTION_EXECUTED = "action_executed"
    SCREEN_DETECTED = "screen_detected"
    METRICS_UPDATED = "metrics_updated"
    ERROR_OCCURRED = "error_occurred"


@dataclass
class DashboardUpdate:
    """A dashboard update event."""
    update_type: DashboardUpdateType
    timestamp: datetime = field(default_factory=datetime.now)
    data: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for JSON serialization."""
        return {
            "type": self.update_type.value,
            "timestamp": self.timestamp.isoformat(),
            "data": self.data,
        }


class EventLoopDashboard:
    """
    Real-time dashboard monitoring for event loop.
    
    Features:
    - Live task tracking
    - Screen state monitoring
    - Performance metrics
    - Action timeline
    - Error alerts
    """
    
    def __init__(self, event_loop):
        """Initialize dashboard.
        
        Args:
            event_loop: ScreenStateEventLoop instance
        """
        self.event_loop = event_loop
        self.update_callbacks: list[Callable] = []
        self.update_history: list[DashboardUpdate] = []
        self.max_history_size = 100
        
        # Subscribe to internal event loop, if events implemented
        self._start_monitoring()
    
    def _start_monitoring(self):
        """Start monitoring event loop."""
        # In a real implementation, would hook into event loop
        # For now, dashboard can be polled or updated manually
        pass
    
    def get_current_status(self) -> Dict[str, Any]:
        """Get current system status.
        
        Returns:
            Status dictionary
        """
        status = self.event_loop.get_status()
        
        return {
            "timestamp": datetime.now().isoformat(),
            "loop_state": status["loop_state"],
            "current_task": status["current_task"],
            "current_screen": status["current_screen"],
            "metrics": status["metrics"],
            "task_count": len(self.event_loop.task_history),
        }
    
    def get_current_metrics(self) -> Dict[str, Any]:
        """Get detailed metrics.
        
        Returns:
            Metrics dictionary
        """
        metrics = self.event_loop.metrics
        
        return {
            "tasks_processed": metrics.tasks_processed,
            "actions_executed": metrics.actions_executed,
            "vision_calls": metrics.vision_calls,
            "planner_calls": metrics.planner_calls,
            "retries_attempted": metrics.retries_attempted,
            "successful_tasks": metrics.successful_tasks,
            "failed_tasks": metrics.failed_tasks,
            "total_time_ms": metrics.total_time_ms,
            "success_rate": metrics.get_summary()["success_rate"],
            "avg_actions_per_task": (
                metrics.actions_executed / metrics.tasks_processed
                if metrics.tasks_processed > 0 else 0
            ),
            "avg_steps_per_task": (
                sum(len(t.get("steps", [])) for t in self.event_loop.task_history)
                / metrics.tasks_processed
                if metrics.tasks_processed > 0 else 0
            ),
        }
    
    def get_recent_actions(self, limit: int = 10) -> list[Dict[str, Any]]:
        """Get recent actions from task history.
        
        Args:
            limit: Number of recent actions to return
            
        Returns:
            List of action objects
        """
        actions = []
        
        for task in self.event_loop.task_history[-5:]:  # Last 5 tasks
            for step in task.get("steps", [])[-limit:]:
                actions.append({
                    "task": task["task"],
                    "step_number": step["step"],
                    "action": step["action"],
                    "screen_state": step["screen"],
                    "success": step["success"],
                })
        
        return actions[-limit:]
    
    def get_task_timeline(self) -> list[Dict[str, Any]]:
        """Get timeline of all tasks.
        
        Returns:
            List of task summaries
        """
        timeline = []
        
        for i, task in enumerate(self.event_loop.task_history):
            timeline.append({
                "task_number": i + 1,
                "description": task["task"],
                "success": task["success"],
                "steps": len(task["steps"]),
                "screen_states": list(set(
                    s["screen"] for s in task["steps"]
                )),
                "error": task.get("error"),
            })
        
        return timeline
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get performance summary.
        
        Returns:
            Performance metrics
        """
        metrics = self.get_current_metrics()
        tasks = self.event_loop.task_history
        
        if not tasks:
            return {
                "status": "No tasks executed yet",
                "metrics": metrics,
            }
        
        avg_task_duration = (
            metrics["total_time_ms"] / len(tasks)
            if tasks else 0
        )
        
        return {
            "total_tasks": len(tasks),
            "successful": metrics["successful_tasks"],
            "failed": metrics["failed_tasks"],
            "success_rate_percent": metrics["success_rate"],
            "total_duration_ms": metrics["total_time_ms"],
            "avg_task_duration_ms": avg_task_duration,
            "total_actions": metrics["actions_executed"],
            "avg_actions_per_task": metrics["avg_actions_per_task"],
            "total_vision_calls": metrics["vision_calls"],
            "avg_vision_calls_per_task": (
                metrics["vision_calls"] / len(tasks)
                if tasks else 0
            ),
            "efficiency_score": (
                (metrics["actions_executed"] / metrics["vision_calls"])
                if metrics["vision_calls"] > 0 else 0.0
            ),
        }
    
    def emit_update(self, update: DashboardUpdate):
        """Emit a dashboard update.
        
        Args:
            update: Update to emit
        """
        # Store in history
        self.update_history.append(update)
        if len(self.update_history) > self.max_history_size:
            self.update_history.pop(0)
        
        # Call registered callbacks
        for callback in self.update_callbacks:
            try:
                callback(update)
            except Exception as e:
                print(f"Dashboard callback error: {e}")
    
    def subscribe(self, callback: Callable):
        """Subscribe to dashboard updates.
        
        Args:
            callback: Function called with DashboardUpdate
        """
        self.update_callbacks.append(callback)
    
    def unsubscribe(self, callback: Callable):
        """Unsubscribe from dashboard updates.
        
        Args:
            callback: Function to remove
        """
        if callback in self.update_callbacks:
            self.update_callbacks.remove(callback)
    
    def get_html_dashboard(self) -> str:
        """Generate HTML dashboard.
        
        Returns:
            HTML string
        """
        status = self.get_current_status()
        metrics = self.get_current_metrics()
        performance = self.get_performance_summary()
        recent_actions = self.get_recent_actions(5)
        
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Event Loop Dashboard</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: 'Segoe UI', sans-serif; background: #0d1117; color: #c9d1d9; }}
        .container {{ max-width: 1400px; margin: 0 auto; padding: 20px; }}
        .header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 30px; border-bottom: 2px solid #30363d; padding-bottom: 20px; }}
        h1 {{ font-size: 2em; color: #58a6ff; }}
        .status-badge {{ 
            display: inline-block; 
            padding: 8px 16px; 
            border-radius: 20px; 
            font-weight: bold; 
            background: #1f6feb; 
            color: white;
        }}
        .status-badge.idle {{ background: #6e40aa; }}
        .status-badge.executing {{ background: #238636; }}
        .status-badge.error {{ background: #da3633; }}
        .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; margin-bottom: 30px; }}
        .card {{ 
            background: #161b22; 
            border: 1px solid #30363d; 
            border-radius: 6px; 
            padding: 20px; 
        }}
        .card h2 {{ font-size: 1.1em; margin-bottom: 15px; color: #58a6ff; }}
        .metric {{ display: flex; justify-content: space-between; margin-bottom: 10px; }}
        .metric-label {{ color: #8b949e; }}
        .metric-value {{ font-weight: bold; color: #c9d1d9; }}
        .action-item {{
            background: #0d1117;
            padding: 10px;
            border-left: 3px solid #58a6ff;
            margin-bottom: 10px;
            border-radius: 3px;
        }}
        .action-success {{ border-left-color: #238636; }}
        .action-failure {{ border-left-color: #da3633; }}
        table {{ width: 100%; border-collapse: collapse; }}
        th, td {{ padding: 10px; text-align: left; border-bottom: 1px solid #30363d; }}
        th {{ background: #0d1117; font-weight: bold; color: #58a6ff; }}
        .timestamp {{ color: #8b949e; font-size: 0.9em; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🤖 Event Loop Dashboard</h1>
            <span class="status-badge {status['loop_state'].lower()}">{status['loop_state'].upper()}</span>
        </div>
        
        <div class="grid">
            <div class="card">
                <h2>Current Task</h2>
                <div class="metric">
                    <span class="metric-label">Task:</span>
                    <span class="metric-value">{status['current_task'] or 'None'}</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Screen:</span>
                    <span class="metric-value">{status['current_screen'] or 'Unknown'}</span>
                </div>
            </div>
            
            <div class="card">
                <h2>Quick Stats</h2>
                <div class="metric">
                    <span class="metric-label">Tasks:</span>
                    <span class="metric-value">{metrics['tasks_processed']}</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Success Rate:</span>
                    <span class="metric-value">{metrics['success_rate']:.1f}%</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Actions:</span>
                    <span class="metric-value">{metrics['actions_executed']}</span>
                </div>
            </div>
            
            <div class="card">
                <h2>Performance</h2>
                <div class="metric">
                    <span class="metric-label">Avg Task Time:</span>
                    <span class="metric-value">{performance.get('avg_task_duration_ms', 0):.0f}ms</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Actions/Task:</span>
                    <span class="metric-value">{metrics['avg_actions_per_task']:.1f}</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Vision Calls:</span>
                    <span class="metric-value">{metrics['vision_calls']}</span>
                </div>
            </div>
        </div>
        
        <div class="card">
            <h2>Recent Actions</h2>
            <div>
"""
        
        if recent_actions:
            for action in recent_actions:
                success_class = "action-success" if action["success"] else "action-failure"
                html += f"""
                <div class="action-item {success_class}">
                    <strong>{action.get('action', {}).get('type', 'unknown')}</strong>
                    &rarr; {action['screen_state']}
                    <span class="timestamp">(Task: {action['task'][:30]}...)</span>
                </div>
"""
        else:
            html += "<p style='color: #8b949e;'>No actions yet</p>"
        
        html += """
            </div>
        </div>
    </div>
</body>
</html>
"""
        return html
    
    def get_json_export(self) -> Dict[str, Any]:
        """Export dashboard as JSON.
        
        Returns:
            JSON-serializable dictionary
        """
        return {
            "timestamp": datetime.now().isoformat(),
            "status": self.get_current_status(),
            "metrics": self.get_current_metrics(),
            "performance": self.get_performance_summary(),
            "timeline": self.get_task_timeline(),
            "recent_actions": self.get_recent_actions(10),
        }
