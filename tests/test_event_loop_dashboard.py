"""Tests for event loop dashboard.

Tests the real-time monitoring and visualization layer.
"""

import pytest
from datetime import datetime
from unittest.mock import Mock

from core.screen.event_loop_dashboard import (
    EventLoopDashboard,
    DashboardUpdate,
    DashboardUpdateType,
)


class TestDashboardUpdate:
    """Test dashboard update events."""
    
    def test_update_creation(self):
        """Test creating a dashboard update."""
        update = DashboardUpdate(
            update_type=DashboardUpdateType.TASK_STARTED,
            data={"task": "Test"}
        )
        assert update.update_type == DashboardUpdateType.TASK_STARTED
        assert update.data["task"] == "Test"
    
    def test_update_to_dict(self):
        """Test converting update to dict."""
        update = DashboardUpdate(
            update_type=DashboardUpdateType.TASK_COMPLETED,
            data={"success": True}
        )
        update_dict = update.to_dict()
        
        assert update_dict["type"] == "task_completed"
        assert update_dict["data"]["success"] is True
        assert "timestamp" in update_dict


class TestEventLoopDashboard:
    """Test event loop dashboard."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_loop = Mock()
        self.mock_loop.get_status = Mock(return_value={
            "loop_state": "idle",
            "current_task": None,
            "current_screen": None,
            "metrics": {
                "tasks_processed": 0,
                "success_rate": 0,
            }
        })
        self.mock_loop.metrics = Mock()
        self.mock_loop.metrics.tasks_processed = 0
        self.mock_loop.metrics.actions_executed = 0
        self.mock_loop.metrics.vision_calls = 0
        self.mock_loop.metrics.planner_calls = 0
        self.mock_loop.metrics.retries_attempted = 0
        self.mock_loop.metrics.successful_tasks = 0
        self.mock_loop.metrics.failed_tasks = 0
        self.mock_loop.metrics.total_time_ms = 0.0
        self.mock_loop.metrics.get_summary = Mock(
            return_value={"success_rate": 0}
        )
        self.mock_loop.task_history = []
        
        self.dashboard = EventLoopDashboard(self.mock_loop)
    
    def test_dashboard_initialization(self):
        """Test dashboard initializes."""
        assert self.dashboard.event_loop == self.mock_loop
        assert len(self.dashboard.update_callbacks) == 0
        assert len(self.dashboard.update_history) == 0
    
    def test_get_current_status(self):
        """Test getting current status."""
        self.mock_loop.get_status = Mock(return_value={
            "loop_state": "executing",
            "current_task": "Test task",
            "current_screen": "CHROME",
            "metrics": {"success_rate": 100}
        })
        
        status = self.dashboard.get_current_status()
        
        assert status["loop_state"] == "executing"
        assert status["current_task"] == "Test task"
        assert status["current_screen"] == "CHROME"
        assert "timestamp" in status
    
    def test_get_current_metrics(self):
        """Test getting metrics."""
        self.mock_loop.metrics.tasks_processed = 10
        self.mock_loop.metrics.successful_tasks = 8
        self.mock_loop.metrics.failed_tasks = 2
        self.mock_loop.metrics.actions_executed = 25
        self.mock_loop.metrics.vision_calls = 15
        
        metrics = self.dashboard.get_current_metrics()
        
        assert metrics["tasks_processed"] == 10
        assert metrics["successful_tasks"] == 8
        assert metrics["actions_executed"] == 25
        assert metrics["avg_actions_per_task"] == 2.5
    
    def test_get_recent_actions_empty(self):
        """Test getting recent actions when none exist."""
        self.mock_loop.task_history = []
        
        actions = self.dashboard.get_recent_actions()
        
        assert actions == []
    
    def test_get_recent_actions_with_history(self):
        """Test getting recent actions from history."""
        self.mock_loop.task_history = [
            {
                "task": "Task 1",
                "steps": [
                    {
                        "step": 1,
                        "action": {"type": "click"},
                        "screen": "CHROME",
                        "success": True
                    }
                ]
            },
            {
                "task": "Task 2",
                "steps": [
                    {
                        "step": 1,
                        "action": {"type": "type"},
                        "screen": "DIALOG",
                        "success": False
                    }
                ]
            }
        ]
        
        actions = self.dashboard.get_recent_actions()
        
        assert len(actions) == 2
        assert actions[0]["action"]["type"] == "click"
        assert actions[1]["action"]["type"] == "type"
    
    def test_get_task_timeline(self):
        """Test getting task timeline."""
        self.mock_loop.task_history = [
            {
                "task": "Open Gmail",
                "success": True,
                "steps": [
                    {"screen": "DESKTOP", "action": {}, "success": True},
                    {"screen": "CHROME", "action": {}, "success": True}
                ],
                "error": None
            },
            {
                "task": "Reply email",
                "success": False,
                "steps": [
                    {"screen": "GMAIL", "action": {}, "success": False}
                ],
                "error": "Timeout"
            }
        ]
        
        timeline = self.dashboard.get_task_timeline()
        
        assert len(timeline) == 2
        assert timeline[0]["description"] == "Open Gmail"
        assert timeline[0]["success"] is True
        assert timeline[1]["error"] == "Timeout"
    
    def test_get_performance_summary_no_tasks(self):
        """Test performance summary with no tasks."""
        self.mock_loop.task_history = []
        
        perf = self.dashboard.get_performance_summary()
        
        assert "No tasks executed yet" in perf["status"]
    
    def test_get_performance_summary_with_tasks(self):
        """Test performance summary with tasks."""
        self.mock_loop.task_history = [
            {"task": "Task", "success": True, "steps": [{"screen": "A"}]},
            {"task": "Task", "success": True, "steps": [{"screen": "B"}]},
        ]
        self.mock_loop.metrics.tasks_processed = 2
        self.mock_loop.metrics.successful_tasks = 2
        self.mock_loop.metrics.failed_tasks = 0
        self.mock_loop.metrics.total_time_ms = 1000
        self.mock_loop.metrics.actions_executed = 4
        self.mock_loop.metrics.vision_calls = 4
        
        perf = self.dashboard.get_performance_summary()
        
        assert perf["total_tasks"] == 2
        assert perf["successful"] == 2
        assert perf["success_rate_percent"] == 0  # Based on get_summary mock
    
    def test_emit_update(self):
        """Test emitting dashboard update."""
        update = DashboardUpdate(
            update_type=DashboardUpdateType.TASK_STARTED,
            data={"task": "Test"}
        )
        
        self.dashboard.emit_update(update)
        
        assert len(self.dashboard.update_history) == 1
        assert self.dashboard.update_history[0] == update
    
    def test_emit_update_history_limit(self):
        """Test update history respects size limit."""
        self.dashboard.max_history_size = 3
        
        for i in range(5):
            update = DashboardUpdate(
                update_type=DashboardUpdateType.ACTION_EXECUTED,
                data={"action_num": i}
            )
            self.dashboard.emit_update(update)
        
        assert len(self.dashboard.update_history) == 3
    
    def test_subscribe_to_updates(self):
        """Test subscribing to dashboard updates."""
        callback_called = {"count": 0}
        
        def test_callback(update):
            callback_called["count"] += 1
        
        self.dashboard.subscribe(test_callback)
        update = DashboardUpdate(
            update_type=DashboardUpdateType.TASK_STARTED
        )
        self.dashboard.emit_update(update)
        
        assert callback_called["count"] == 1
    
    def test_unsubscribe_from_updates(self):
        """Test unsubscribing from updates."""
        callback_called = {"count": 0}
        
        def test_callback(update):
            callback_called["count"] += 1
        
        self.dashboard.subscribe(test_callback)
        self.dashboard.unsubscribe(test_callback)
        
        update = DashboardUpdate(
            update_type=DashboardUpdateType.TASK_STARTED
        )
        self.dashboard.emit_update(update)
        
        assert callback_called["count"] == 0
    
    def test_subscribe_multiple_callbacks(self):
        """Test multiple callbacks are called."""
        calls_1 = {"count": 0}
        calls_2 = {"count": 0}
        
        def callback1(update):
            calls_1["count"] += 1
        
        def callback2(update):
            calls_2["count"] += 1
        
        self.dashboard.subscribe(callback1)
        self.dashboard.subscribe(callback2)
        
        update = DashboardUpdate(
            update_type=DashboardUpdateType.TASK_STARTED
        )
        self.dashboard.emit_update(update)
        
        assert calls_1["count"] == 1
        assert calls_2["count"] == 1
    
    def test_get_html_dashboard_no_actions(self):
        """Test HTML dashboard generation without actions."""
        html = self.dashboard.get_html_dashboard()
        
        assert "<!DOCTYPE html>" in html
        assert "Event Loop Dashboard" in html
        assert "idle" in html.lower()
    
    def test_get_html_dashboard_with_actions(self):
        """Test HTML dashboard includes recent actions."""
        self.mock_loop.task_history = [
            {
                "task": "Test task",
                "steps": [
                    {
                        "step": 1,
                        "action": {"type": "click"},
                        "screen": "CHROME",
                        "success": True
                    }
                ]
            }
        ]
        
        html = self.dashboard.get_html_dashboard()
        
        assert "click" in html.lower()
        assert "chrome" in html.lower()
    
    def test_get_json_export(self):
        """Test JSON export."""
        self.mock_loop.task_history = []
        
        json_data = self.dashboard.get_json_export()
        
        assert "timestamp" in json_data
        assert "status" in json_data
        assert "metrics" in json_data
        assert "performance" in json_data
        assert "timeline" in json_data
        assert "recent_actions" in json_data
    
    def test_json_export_with_data(self):
        """Test JSON export with populated data."""
        self.mock_loop.task_history = [
            {
                "task": "Task 1",
                "success": True,
                "steps": [
                    {"step": 1, "action": {}, "screen": "A", "success": True}
                ],
                "error": None
            }
        ]
        
        json_data = self.dashboard.get_json_export()
        
        assert len(json_data["timeline"]) == 1
        assert json_data["timeline"][0]["description"] == "Task 1"
    
    def test_metrics_with_zero_division_protection(self):
        """Test metrics handle zero division gracefully."""
        self.mock_loop.metrics.tasks_processed = 0
        self.mock_loop.metrics.actions_executed = 0
        
        metrics = self.dashboard.get_current_metrics()
        
        assert metrics["avg_actions_per_task"] == 0  # No division by zero
    
    def test_callback_exception_handling(self):
        """Test callback exceptions don't break dashboard."""
        def bad_callback(update):
            raise RuntimeError("Callback error")
        
        def good_callback(update):
            pass
        
        good_called = {"count": 0}
        
        def recording_callback(update):
            good_called["count"] += 1
        
        self.dashboard.subscribe(bad_callback)
        self.dashboard.subscribe(recording_callback)
        
        update = DashboardUpdate(
            update_type=DashboardUpdateType.TASK_STARTED
        )
        self.dashboard.emit_update(update)
        
        # Good callback should still be called despite bad callback
        assert good_called["count"] == 1
