"""Tests for Action Logger System
=================================

Tests automation action tracking, history, and analytics.
"""

import pytest
from datetime import datetime
from core.screen.action_logger import ActionRecord, ActionLogger


class TestActionRecord:
    """Tests for ActionRecord dataclass."""
    
    def test_action_record_creation(self):
        """Test creating an action record."""
        record = ActionRecord(
            action_type="click",
            target="button",
            value="(100, 50)"
        )
        
        assert record.action_type == "click"
        assert record.target == "button"
        assert record.value == "(100, 50)"
        assert record.success is True
        assert record.error is None
    
    def test_action_record_with_error(self):
        """Test creating a failed action record."""
        record = ActionRecord(
            action_type="click",
            target="button",
            success=False,
            error="Element not found"
        )
        
        assert not record.success
        assert record.error == "Element not found"
    
    def test_action_record_to_dict(self):
        """Test converting record to dictionary."""
        record = ActionRecord(
            action_type="type",
            value="test text",
            screen_state="CHROME_BROWSER"
        )
        
        data = record.to_dict()
        
        assert isinstance(data, dict)
        assert data["action_type"] == "type"
        assert data["value"] == "test text"
        assert data["screen_state"] == "CHROME_BROWSER"
        assert "timestamp" in data
    
    def test_action_record_timestamp(self):
        """Test action record timestamp."""
        before = datetime.now()
        record = ActionRecord(action_type="click")
        after = datetime.now()
        
        assert before <= record.timestamp <= after
    
    def test_action_record_with_metadata(self):
        """Test action record with additional metadata."""
        record = ActionRecord(
            action_type="click",
            metadata={"screen_size": (1920, 1080), "browser": "chrome"}
        )
        
        assert record.metadata["screen_size"] == (1920, 1080)
        assert record.metadata["browser"] == "chrome"


class TestActionLoggerInitialization:
    """Tests for ActionLogger initialization."""
    
    def test_logger_initialization(self):
        """Test creating action logger."""
        logger = ActionLogger()
        
        assert logger.max_history == 1000
        assert logger.history == []
    
    def test_logger_with_custom_max(self):
        """Test creating logger with custom max history."""
        logger = ActionLogger(max_history=100)
        
        assert logger.max_history == 100


class TestActionLogging:
    """Tests for logging actions."""
    
    def test_log_action(self):
        """Test logging a single action."""
        logger = ActionLogger()
        
        record = logger.log_action(
            action_type="click",
            target="button",
            value="(100, 50)"
        )
        
        assert record.action_type == "click"
        assert len(logger.history) == 1
        assert logger.history[0] is record
    
    def test_log_click(self):
        """Test logging a click action."""
        logger = ActionLogger()
        
        record = logger.log_click(
            target="submit_button",
            x=100,
            y=200
        )
        
        assert record.action_type == "click"
        assert record.target == "submit_button"
        assert "(100, 200)" in record.value
    
    def test_log_type(self):
        """Test logging a type action."""
        logger = ActionLogger()
        
        record = logger.log_type(value="Hello World")
        
        assert record.action_type == "type"
        assert record.value == "Hello World"
    
    def test_log_key(self):
        """Test logging a key press."""
        logger = ActionLogger()
        
        record = logger.log_key(key="Return")
        
        assert record.action_type == "key"
        assert record.value == "Return"
    
    def test_log_failed_action(self):
        """Test logging a failed action."""
        logger = ActionLogger()
        
        record = logger.log_action(
            action_type="click",
            target="missing_button",
            success=False,
            error="Element not found"
        )
        
        assert not record.success
        assert record.error == "Element not found"
        assert len(logger.get_failed_actions()) == 1
    
    def test_log_multiple_actions(self):
        """Test logging multiple actions."""
        logger = ActionLogger()
        
        logger.log_click(target="btn1", x=10, y=20)
        logger.log_type(value="test")
        logger.log_key(key="Enter")
        
        assert len(logger.history) == 3
        assert logger.history[0].action_type == "click"
        assert logger.history[1].action_type == "type"
        assert logger.history[2].action_type == "key"


class TestActionHistory:
    """Tests for action history retrieval."""
    
    def test_get_history(self):
        """Test getting full history."""
        logger = ActionLogger()
        
        logger.log_click(target="btn", x=0, y=0)
        logger.log_type(value="text")
        logger.log_key(key="Tab")
        
        history = logger.get_history()
        
        assert len(history) == 3
        assert history[0].action_type == "click"
    
    def test_get_history_with_limit(self):
        """Test getting limited history."""
        logger = ActionLogger()
        
        for i in range(10):
            logger.log_click(target=f"btn{i}", x=i, y=i)
        
        history = logger.get_history(limit=3)
        
        assert len(history) == 3
        assert history[-1].target.endswith("9")  # Last one
    
    def test_get_last_action(self):
        """Test getting last action."""
        logger = ActionLogger()
        
        logger.log_click(target="btn1", x=0, y=0)
        logger.log_type(value="text")
        
        last = logger.get_last_action()
        
        assert last.action_type == "type"
        assert last.value == "text"
    
    def test_get_last_action_empty(self):
        """Test getting last action when history is empty."""
        logger = ActionLogger()
        
        last = logger.get_last_action()
        
        assert last is None
    
    def test_get_actions_by_type(self):
        """Test filtering actions by type."""
        logger = ActionLogger()
        
        logger.log_click(target="btn1", x=0, y=0)
        logger.log_click(target="btn2", x=10, y=10)
        logger.log_type(value="text")
        logger.log_key(key="Tab")
        logger.log_click(target="btn3", x=20, y=20)
        
        clicks = logger.get_actions_by_type("click")
        
        assert len(clicks) == 3
        assert all(a.action_type == "click" for a in clicks)
    
    def test_get_failed_actions(self):
        """Test getting failed actions."""
        logger = ActionLogger()
        
        logger.log_click(target="btn", x=0, y=0)
        logger.log_action("click", success=False, error="Not found")
        logger.log_type(value="text")
        logger.log_action("key", success=False, error="Timeout")
        
        failed = logger.get_failed_actions()
        
        assert len(failed) == 2
        assert all(not a.success for a in failed)


class TestActionSummary:
    """Tests for action history summary."""
    
    def test_get_summary_empty(self):
        """Test summary of empty logger."""
        logger = ActionLogger()
        
        summary = logger.get_summary()
        
        assert summary["total_actions"] == 0
        assert summary["failed_actions"] == 0
        assert summary["success_rate"] == 1.0
    
    def test_get_summary_all_success(self):
        """Test summary when all actions succeed."""
        logger = ActionLogger()
        
        for i in range(5):
            logger.log_click(target=f"btn{i}", x=i, y=i)
        
        summary = logger.get_summary()
        
        assert summary["total_actions"] == 5
        assert summary["failed_actions"] == 0
        assert summary["success_rate"] == 1.0
        assert summary["action_counts"]["click"] == 5
    
    def test_get_summary_with_failures(self):
        """Test summary with failed actions."""
        logger = ActionLogger()
        
        logger.log_click(target="btn", x=0, y=0)
        logger.log_click(target="btn", x=0, y=0)
        logger.log_action("click", success=False, error="Failed")
        logger.log_action("type", success=False, error="Failed")
        
        summary = logger.get_summary()
        
        assert summary["total_actions"] == 4
        assert summary["failed_actions"] == 2
        assert summary["success_rate"] == 0.5
    
    def test_action_counts(self):
        """Test action type counting."""
        logger = ActionLogger()
        
        logger.log_click(target="btn1", x=0, y=0)
        logger.log_click(target="btn2", x=0, y=0)
        logger.log_type(value="text")
        logger.log_key(key="Enter")
        logger.log_key(key="Tab")
        
        summary = logger.get_summary()
        
        assert summary["action_counts"]["click"] == 2
        assert summary["action_counts"]["type"] == 1
        assert summary["action_counts"]["key"] == 2


class TestHistoryManagement:
    """Tests for history management."""
    
    def test_max_history_limit(self):
        """Test that history respects max_history limit."""
        logger = ActionLogger(max_history=5)
        
        for i in range(10):
            logger.log_click(target=f"btn{i}", x=i, y=i)
        
        history = logger.get_history()
        
        assert len(history) == 5
        # Most recent entries should remain
        assert "btn9" in history[-1].target
    
    def test_clear_history(self):
        """Test clearing history."""
        logger = ActionLogger()
        
        logger.log_click(target="btn", x=0, y=0)
        logger.log_type(value="text")
        
        assert len(logger.history) == 2
        
        logger.clear_history()
        
        assert len(logger.history) == 0
    
    def test_history_order(self):
        """Test that history maintains insertion order."""
        logger = ActionLogger()
        
        actions = ["click", "type", "key", "click", "type"]
        for action in actions:
            if action == "click":
                logger.log_click(target="btn", x=0, y=0)
            elif action == "type":
                logger.log_type(value="text")
            else:
                logger.log_key(key="Enter")
        
        history = logger.get_history()
        
        assert [h.action_type for h in history] == actions


class TestHistoryExport:
    """Tests for history export formats."""
    
    def test_export_json(self):
        """Test exporting history as JSON."""
        logger = ActionLogger()
        
        logger.log_click(target="btn", x=100, y=200)
        logger.log_type(value="test")
        
        json_str = logger.export_json()
        
        assert isinstance(json_str, str)
        assert "click" in json_str
        assert "type" in json_str
        assert len(json_str) > 0
    
    def test_export_csv(self):
        """Test exporting history as CSV."""
        logger = ActionLogger()
        
        logger.log_click(target="btn", x=100, y=200)
        logger.log_type(value="test")
        
        csv_str = logger.export_csv()
        
        assert isinstance(csv_str, str)
        assert "action_type" in csv_str
        assert "click" in csv_str
        assert len(csv_str) > 0
    
    def test_export_csv_empty(self):
        """Test exporting empty CSV."""
        logger = ActionLogger()
        
        csv_str = logger.export_csv()
        
        assert csv_str == ""
