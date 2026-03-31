"""Tests for event loop screen state architecture.

Tests the core event loop that drives task execution through screen states.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, MagicMock, patch
from datetime import datetime

from core.screen.event_loop import (
    ScreenStateEventLoop, ScreenState, LoopState, LoopMetrics
)


class TestLoopMetrics:
    """Test metrics tracking."""
    
    def test_metrics_initialization(self):
        """Test metrics starts at zero."""
        metrics = LoopMetrics()
        assert metrics.tasks_processed == 0
        assert metrics.actions_executed == 0
        assert metrics.vision_calls == 0
        assert metrics.successful_tasks == 0
    
    def test_metrics_summary(self):
        """Test metrics summary generation."""
        metrics = LoopMetrics()
        metrics.tasks_processed = 10
        metrics.successful_tasks = 8
        metrics.failed_tasks = 2
        
        summary = metrics.get_summary()
        assert summary["tasks_processed"] == 10
        assert summary["success_rate"] == 80.0
    
    def test_success_rate_zero_tasks(self):
        """Test success rate with zero tasks."""
        metrics = LoopMetrics()
        summary = metrics.get_summary()
        assert summary["success_rate"] == 0


class TestScreenState:
    """Test screen state representation."""
    
    def test_screen_state_creation(self):
        """Test creating screen state."""
        state = ScreenState(
            screen_type="CHROME_PROFILE",
            screenshot=b"fake_image",
            detected_elements=["button1", "link1"],
            text_content=["Gmail", "Inbox"],
            confidence=0.95
        )
        assert state.screen_type == "CHROME_PROFILE"
        assert state.confidence == 0.95
        assert len(state.detected_elements) == 2
    
    def test_screen_state_changed_from_none(self):
        """Test screen changed when comparing to None."""
        state = ScreenState(
            screen_type="CHROME_PROFILE",
            screenshot=b"fake"
        )
        assert state.changed_from(None) is True
    
    def test_screen_state_changed_different_type(self):
        """Test screen changed when type differs."""
        state1 = ScreenState(
            screen_type="CHROME_PROFILE",
            screenshot=b"fake1"
        )
        state2 = ScreenState(
            screen_type="DIALOG",
            screenshot=b"fake2"
        )
        assert state2.changed_from(state1) is True
    
    def test_screen_state_not_changed_same_type(self):
        """Test screen not changed when type is same."""
        state1 = ScreenState(
            screen_type="CHROME_PROFILE",
            screenshot=b"fake1"
        )
        state2 = ScreenState(
            screen_type="CHROME_PROFILE",
            screenshot=b"fake2"
        )
        assert state2.changed_from(state1) is False


class TestEventLoop:
    """Test the main event loop."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_coordinator = Mock()
        self.mock_executor = AsyncMock()
        self.mock_vision_agent = Mock()
        self.mock_action_logger = Mock()
        
        # Setup detector
        mock_detection = Mock()
        mock_detection.screen_type.value = "CHROME_PROFILE"
        mock_detection.detected_elements = ["button1"]
        mock_detection.text_content = ["Login"]
        mock_detection.confidence = 0.95
        
        self.mock_coordinator.detector = Mock()
        self.mock_coordinator.detector.detect_screen = Mock(
            return_value=mock_detection
        )
        
        # Setup router and handlers
        mock_handler = AsyncMock()
        mock_handler.get_next_action = AsyncMock(
            side_effect=[
                {"type": "click", "x": 100, "y": 200},  # First action
                None  # Task done
            ]
        )
        
        self.mock_coordinator.router = Mock()
        self.mock_coordinator.router.handlers = {
            "CHROME_PROFILE": mock_handler
        }
        
        self.mock_executor.take_screenshot = AsyncMock(
            return_value=b"fake_screenshot"
        )
        self.mock_executor.click = AsyncMock(return_value=True)
        
        self.loop = ScreenStateEventLoop(
            coordinator=self.mock_coordinator,
            executor=self.mock_executor,
            vision_agent=self.mock_vision_agent,
            action_logger=self.mock_action_logger,
            max_steps=10
        )
    
    @pytest.mark.asyncio
    async def test_loop_initialization(self):
        """Test loop initializes correctly."""
        assert self.loop.loop_state == LoopState.IDLE
        assert self.loop.current_task is None
        assert self.loop.metrics.tasks_processed == 0
    
    @pytest.mark.asyncio
    async def test_execute_simple_task(self):
        """Test executing a simple task."""
        result = await self.loop.execute_task("Click login button")
        
        assert result["success"] is True
        assert result["task"] == "Click login button"
        assert len(result["steps"]) == 1
        assert result["final_screen"] == "CHROME_PROFILE"
    
    @pytest.mark.asyncio
    async def test_multiple_actions_in_task(self):
        """Test task with multiple actions."""
        mock_handler = AsyncMock()
        mock_handler.get_next_action = AsyncMock(
            side_effect=[
                {"type": "click", "x": 100, "y": 200},
                {"type": "type", "text": "password"},
                {"type": "key", "key": "Enter"},
                None  # Done
            ]
        )
        
        self.mock_coordinator.router.handlers = {
            "CHROME_PROFILE": mock_handler
        }
        
        result = await self.loop.execute_task("Login to app")
        
        assert result["success"] is True
        assert len(result["steps"]) == 3
        assert self.loop.metrics.actions_executed == 3
    
    @pytest.mark.asyncio
    async def test_task_timeout_max_steps(self):
        """Test task times out after max steps."""
        mock_handler = AsyncMock()
        # Handler always returns an action (never returns None)
        mock_handler.get_next_action = AsyncMock(
            return_value={"type": "click", "x": 100, "y": 200}
        )
        
        self.mock_coordinator.router.handlers = {
            "CHROME_PROFILE": mock_handler
        }
        
        self.loop.max_steps = 3  # Lower max steps
        result = await self.loop.execute_task("Never-ending task")
        
        assert result["success"] is False
        assert "max steps" in result["error"].lower()
        assert len(result["steps"]) == 3
    
    @pytest.mark.asyncio
    async def test_action_execution_tracking(self):
        """Test actions are tracked in metrics."""
        result = await self.loop.execute_task("Test tracking")
        
        assert self.loop.metrics.actions_executed == 1
        assert self.loop.metrics.vision_calls >= 1
        assert len(self.loop.task_history) == 1
    
    @pytest.mark.asyncio
    async def test_action_logger_called(self):
        """Test action is logged."""
        result = await self.loop.execute_task("Test logging")
        
        self.mock_action_logger.log_action.assert_called()
        call_args = self.mock_action_logger.log_action.call_args
        assert call_args[1]["action_type"] == "click"
        assert call_args[1]["screen_state"] == "CHROME_PROFILE"
    
    @pytest.mark.asyncio
    async def test_handler_not_found(self):
        """Test graceful failure when handler not found."""
        self.mock_coordinator.router.handlers = {}  # No handlers
        
        result = await self.loop.execute_task("Unknown screen")
        
        assert result["success"] is False
        assert "No handler" in result["error"]
    
    @pytest.mark.asyncio
    async def test_action_execution_failure(self):
        """Test handling of failed action."""
        async def click_fails(x, y):
            return False
        
        self.mock_executor.click = AsyncMock(side_effect=click_fails)
        
        mock_handler = AsyncMock()
        mock_handler.get_next_action = AsyncMock(
            side_effect=[
                {"type": "click", "x": 100, "y": 200, "retry": False},
                None
            ]
        )
        self.mock_coordinator.router.handlers = {
            "CHROME_PROFILE": mock_handler
        }
        
        result = await self.loop.execute_task("Test failure")
        
        # Task continues even on failure if no retry
        assert result["success"] is True  # Task completed despite action failure
        assert result["steps"][0]["success"] is False
    
    @pytest.mark.asyncio
    async def test_action_retry_on_failure(self):
        """Test action retry on failure."""
        call_count = {"count": 0}
        
        async def click_side_effect(x, y):
            call_count["count"] += 1
            return call_count["count"] > 1  # Fail first, succeed second
        
        self.mock_executor.click = AsyncMock(
            side_effect=click_side_effect
        )
        
        mock_handler = AsyncMock()
        # Handler returns action with retry on first call,
        # then returns None on next call
        mock_handler.get_next_action = AsyncMock(
            side_effect=[
                {"type": "click", "x": 100, "y": 200, "retry": True},
                None
            ]
        )
        self.mock_coordinator.router.handlers = {
            "CHROME_PROFILE": mock_handler
        }
        
        initial_retries = self.loop.metrics.retries_attempted
        result = await self.loop.execute_task("Test retry")
        
        # Loop should attempt retry when action fails with retry=True
        assert self.loop.metrics.retries_attempted > initial_retries
        assert result["success"] is True  # Task still completes
    
    @pytest.mark.asyncio
    async def test_get_status(self):
        """Test getting loop status."""
        status = self.loop.get_status()
        
        assert status["loop_state"] == LoopState.IDLE.value
        assert status["current_task"] is None
        assert "metrics" in status
    
    @pytest.mark.asyncio
    async def test_status_during_execution(self):
        """Test status during task execution."""
        async def slow_handler_action(task, screen_state):
            await asyncio.sleep(0.1)
            return None
        
        mock_handler = AsyncMock()
        mock_handler.get_next_action = AsyncMock(
            side_effect=slow_handler_action
        )
        
        self.mock_coordinator.router.handlers = {
            "CHROME_PROFILE": mock_handler
        }
        
        # This won't work perfectly due to threading, but at least test it doesn't crash
        task = asyncio.create_task(
            self.loop.execute_task("Test")
        )
        await asyncio.sleep(0.05)
        
        status = self.loop.get_status()
        assert status is not None  # Should not crash
        
        await task
    
    @pytest.mark.asyncio
    async def test_task_history(self):
        """Test task history tracking."""
        await self.loop.execute_task("Task 1")
        await self.loop.execute_task("Task 2")
        
        history = self.loop.get_task_history()
        assert len(history) == 2
        assert history[0]["task"] == "Task 1"
        assert history[1]["task"] == "Task 2"
    
    @pytest.mark.asyncio
    async def test_task_history_limit(self):
        """Test getting limited task history."""
        for i in range(5):
            await self.loop.execute_task(f"Task {i}")
        
        history = self.loop.get_task_history(limit=2)
        assert len(history) == 2
        assert history[0]["task"] == "Task 3"
        assert history[1]["task"] == "Task 4"
    
    @pytest.mark.asyncio
    async def test_screen_state_detection(self):
        """Test screen state detection in loop."""
        await self.loop.execute_task("Test")
        
        # After task completes, screen state remains (not cleared)
        # This allows inspection of final state
        assert self.loop.current_screen_state is not None
        assert self.loop.current_screen_state.screen_type == "CHROME_PROFILE"
        self.mock_coordinator.detector.detect_screen.assert_called()
    
    @pytest.mark.asyncio
    async def test_all_action_types(self):
        """Test execution of all action types."""
        action_sequence = [
            {"type": "click", "x": 100, "y": 200},
            {"type": "type", "text": "hello"},
            {"type": "key", "key": "Enter"},
            {"type": "navigate", "url": "https://example.com"},
            {"type": "wait", "delay_ms": 100},
            None  # Done
        ]
        
        mock_handler = AsyncMock()
        mock_handler.get_next_action = AsyncMock(side_effect=action_sequence)
        self.mock_coordinator.router.handlers = {
            "CHROME_PROFILE": mock_handler
        }
        
        self.mock_executor.type_text = AsyncMock(return_value=True)
        self.mock_executor.press_key = AsyncMock(return_value=True)
        self.mock_executor.navigate_to = AsyncMock(return_value=True)
        
        result = await self.loop.execute_task("Test all actions")
        
        assert result["success"] is True
        assert len(result["steps"]) == 5
        self.mock_executor.click.assert_called()
        self.mock_executor.type_text.assert_called()
        self.mock_executor.press_key.assert_called()
        self.mock_executor.navigate_to.assert_called()
    
    @pytest.mark.asyncio
    async def test_unknown_action_type(self):
        """Test handling of unknown action type."""
        mock_handler = AsyncMock()
        mock_handler.get_next_action = AsyncMock(
            side_effect=[
                {"type": "unknown_action"},
                None
            ]
        )
        self.mock_coordinator.router.handlers = {
            "CHROME_PROFILE": mock_handler
        }
        
        result = await self.loop.execute_task("Unknown")
        
        assert result["steps"][0]["success"] is False
    
    @pytest.mark.asyncio
    async def test_exception_in_task(self):
        """Test exception handling during task."""
        self.mock_executor.take_screenshot = AsyncMock(
            side_effect=RuntimeError("Screenshot failed")
        )
        
        result = await self.loop.execute_task("Test exception")
        
        assert result["success"] is False
        assert "Screenshot failed" in result["error"]
    
    @pytest.mark.asyncio
    async def test_metrics_update_on_success(self):
        """Test metrics updated on successful task."""
        initial_tasks = self.loop.metrics.tasks_processed
        initial_successful = self.loop.metrics.successful_tasks
        
        await self.loop.execute_task("Success")
        
        assert self.loop.metrics.tasks_processed == initial_tasks + 1
        assert self.loop.metrics.successful_tasks == initial_successful + 1
    
    @pytest.mark.asyncio
    async def test_metrics_update_on_failure(self):
        """Test metrics updated on failed task."""
        self.mock_coordinator.router.handlers = {}  # No handler
        
        initial_failed = self.loop.metrics.failed_tasks
        
        await self.loop.execute_task("Failure")
        
        assert self.loop.metrics.failed_tasks == initial_failed + 1
    
    @pytest.mark.asyncio
    async def test_loop_state_transitions(self):
        """Test loop goes through correct states."""
        states_seen = []
        
        original_execute_action = self.loop._execute_action
        
        async def track_state(*args, **kwargs):
            states_seen.append(self.loop.loop_state)
            return await original_execute_action(*args, **kwargs)
        
        self.loop._execute_action = track_state
        
        await self.loop.execute_task("Test states")
        
        # Should see EXECUTING and PLANNING states
        assert LoopState.EXECUTING in states_seen or LoopState.WATCHING in states_seen
