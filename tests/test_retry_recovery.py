"""Tests for Retry and Recovery System
=====================================

Tests retry policies, recovery actions, and task execution.
"""

import pytest
import asyncio
from core.screen.retry_recovery import (
    RetryStrategy,
    RetryPolicy,
    RecoveryAction,
    RecoveryAttempt,
    TaskRetry,
    RecoveryManager,
    ReliableTaskExecutor
)


class TestRetryStrategy:
    """Tests for RetryStrategy enum."""
    
    def test_retry_strategy_values(self):
        """Test retry strategy enum values."""
        assert RetryStrategy.IMMEDIATE.value == "immediate"
        assert RetryStrategy.EXPONENTIAL_BACKOFF.value == "exponential_backoff"
        assert RetryStrategy.LINEAR_BACKOFF.value == "linear_backoff"
        assert RetryStrategy.FIXED_DELAY.value == "fixed_delay"


class TestRetryPolicy:
    """Tests for RetryPolicy configuration."""
    
    def test_policy_defaults(self):
        """Test default retry policy."""
        policy = RetryPolicy()
        
        assert policy.max_attempts == 3
        assert policy.initial_delay_ms == 100
        assert policy.max_delay_ms == 5000
        assert policy.strategy == RetryStrategy.EXPONENTIAL_BACKOFF
    
    def test_policy_custom_values(self):
        """Test custom retry policy."""
        policy = RetryPolicy(
            max_attempts=5,
            initial_delay_ms=200,
            strategy=RetryStrategy.LINEAR_BACKOFF
        )
        
        assert policy.max_attempts == 5
        assert policy.initial_delay_ms == 200
        assert policy.strategy == RetryStrategy.LINEAR_BACKOFF
    
    def test_get_delay_immediate(self):
        """Test immediate retry delay."""
        policy = RetryPolicy(strategy=RetryStrategy.IMMEDIATE)
        
        assert policy.get_delay_ms(0) == 0
        assert policy.get_delay_ms(1) == 0
        assert policy.get_delay_ms(5) == 0
    
    def test_get_delay_exponential(self):
        """Test exponential backoff delay."""
        policy = RetryPolicy(
            strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
            initial_delay_ms=100,
            backoff_multiplier=2.0
        )
        
        assert policy.get_delay_ms(0) == 100  # 100 * 2^0
        assert policy.get_delay_ms(1) == 200  # 100 * 2^1
        assert policy.get_delay_ms(2) == 400  # 100 * 2^2
    
    def test_get_delay_linear(self):
        """Test linear backoff delay."""
        policy = RetryPolicy(
            strategy=RetryStrategy.LINEAR_BACKOFF,
            initial_delay_ms=100
        )
        
        assert policy.get_delay_ms(0) == 100  # 100 * 1
        assert policy.get_delay_ms(1) == 200  # 100 * 2
        assert policy.get_delay_ms(2) == 300  # 100 * 3
    
    def test_get_delay_fixed(self):
        """Test fixed delay."""
        policy = RetryPolicy(
            strategy=RetryStrategy.FIXED_DELAY,
            initial_delay_ms=500
        )
        
        assert policy.get_delay_ms(0) == 500
        assert policy.get_delay_ms(1) == 500
        assert policy.get_delay_ms(5) == 500
    
    def test_get_delay_respects_max(self):
        """Test delay respects max_delay_ms."""
        policy = RetryPolicy(
            strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
            initial_delay_ms=1000,
            max_delay_ms=2000,
            backoff_multiplier=2.0
        )
        
        assert policy.get_delay_ms(0) == 1000
        assert policy.get_delay_ms(1) == 2000  # Would be 2000
        assert policy.get_delay_ms(2) == 2000  # Would be 4000, capped at 2000


class TestRecoveryAction:
    """Tests for RecoveryAction enum."""
    
    def test_recovery_action_values(self):
        """Test recovery action enum values."""
        assert RecoveryAction.RETRY.value == "retry"
        assert RecoveryAction.PRESS_ESCAPE.value == "press_escape"
        assert RecoveryAction.REFRESH_PAGE.value == "refresh_page"


class TestRecoveryAttempt:
    """Tests for RecoveryAttempt dataclass."""
    
    def test_recovery_attempt_creation(self):
        """Test creating recovery attempt."""
        from datetime import datetime
        
        attempt = RecoveryAttempt(
            action=RecoveryAction.RETRY,
            timestamp=datetime.now(),
            success=True
        )
        
        assert attempt.action == RecoveryAction.RETRY
        assert attempt.success is True
        assert attempt.error is None


class TestTaskRetry:
    """Tests for TaskRetry."""
    
    def test_task_retry_initialization(self):
        """Test TaskRetry initialization."""
        retry = TaskRetry()
        
        assert retry.policy.max_attempts == 3
        assert retry.attempts == 0
    
    def test_task_retry_with_custom_policy(self):
        """Test TaskRetry with custom policy."""
        policy = RetryPolicy(max_attempts=5)
        retry = TaskRetry(policy)
        
        assert retry.policy.max_attempts == 5
    
    @pytest.mark.asyncio
    async def test_execute_succeeds_immediately(self):
        """Test task that succeeds immediately."""
        async def success_task():
            return "result"
        
        retry = TaskRetry()
        success, result, error = await retry.execute_with_retry(success_task)
        
        assert success is True
        assert result == "result"
        assert error is None
        assert retry.attempts == 1
    
    @pytest.mark.asyncio
    async def test_execute_fails(self):
        """Test task that always fails."""
        async def fail_task():
            raise Exception("Task failed")
        
        policy = RetryPolicy(max_attempts=2, initial_delay_ms=10)
        retry = TaskRetry(policy)
        
        success, result, error = await retry.execute_with_retry(fail_task)
        
        assert success is False
        assert result is None
        assert error is not None
        assert retry.attempts == 2
    
    @pytest.mark.asyncio
    async def test_execute_succeeds_after_retries(self):
        """Test task that succeeds after retries."""
        attempt_count = 0
        
        async def eventually_succeeds():
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count < 3:
                raise Exception("Not yet")
            return "success"
        
        policy = RetryPolicy(max_attempts=5, initial_delay_ms=10)
        retry = TaskRetry(policy)
        
        success, result, error = await retry.execute_with_retry(eventually_succeeds)
        
        assert success is True
        assert result == "success"
        assert retry.attempts == 3
    
    def test_get_attempts(self):
        """Test getting attempt count."""
        retry = TaskRetry()
        
        assert retry.get_attempts() == 0


class TestRecoveryManager:
    """Tests for RecoveryManager."""
    
    def test_recovery_manager_initialization(self):
        """Test RecoveryManager initialization."""
        manager = RecoveryManager()
        
        assert manager.executor is None
        assert manager.recovery_history == []
    
    def test_recovery_manager_with_executor(self):
        """Test RecoveryManager with executor."""
        class MockExecutor:
            pass
        
        executor = MockExecutor()
        manager = RecoveryManager(executor=executor)
        
        assert manager.executor is executor
    
    @pytest.mark.asyncio
    async def test_attempt_retry_recovery(self):
        """Test RETRY recovery action."""
        manager = RecoveryManager()
        
        result = await manager.attempt_recovery(RecoveryAction.RETRY)
        
        assert result is True
    
    @pytest.mark.asyncio
    async def test_attempt_wait_recovery(self):
        """Test WAIT recovery action."""
        manager = RecoveryManager()
        
        result = await manager.attempt_recovery(RecoveryAction.WAIT, delay_ms=10)
        
        assert result is True
    
    @pytest.mark.asyncio
    async def test_attempt_press_escape_recovery(self):
        """Test PRESS_ESCAPE recovery action."""
        class MockExecutor:
            async def press_key(self, key):
                pass
        
        manager = RecoveryManager(executor=MockExecutor())
        
        result = await manager.attempt_recovery(RecoveryAction.PRESS_ESCAPE)
        
        assert result is True
    
    def test_get_recovery_history(self):
        """Test getting recovery history."""
        manager = RecoveryManager()
        
        history = manager.get_recovery_history()
        
        assert isinstance(history, list)
        assert len(history) == 0
    
    def test_get_successful_recoveries(self):
        """Test counting successful recoveries."""
        manager = RecoveryManager()
        
        # Add some attempts
        manager._record_attempt(RecoveryAction.RETRY, success=True)
        manager._record_attempt(RecoveryAction.RETRY, success=False)
        manager._record_attempt(RecoveryAction.WAIT, success=True)
        
        successful = manager.get_successful_recoveries()
        
        assert successful == 2
    
    def test_get_failed_recoveries(self):
        """Test counting failed recoveries."""
        manager = RecoveryManager()
        
        manager._record_attempt(RecoveryAction.RETRY, success=True)
        manager._record_attempt(RecoveryAction.RETRY, success=False)
        manager._record_attempt(RecoveryAction.WAIT, success=False)
        
        failed = manager.get_failed_recoveries()
        
        assert failed == 2


class TestReliableTaskExecutor:
    """Tests for ReliableTaskExecutor."""
    
    def test_executor_initialization(self):
        """Test executor initialization."""
        executor = ReliableTaskExecutor()
        
        assert executor.executor is None
        assert executor.retry is not None
        assert executor.recovery is not None
    
    @pytest.mark.asyncio
    async def test_execute_task_success(self):
        """Test executing successful task."""
        async def success_task():
            return "result"
        
        executor = ReliableTaskExecutor()
        
        success, result, error = await executor.execute_task(success_task)
        
        assert success is True
        assert result == "result"
        assert error is None
    
    @pytest.mark.asyncio
    async def test_execute_task_failure(self):
        """Test executing failing task."""
        async def fail_task():
            raise Exception("Task failed")
        
        policy = RetryPolicy(max_attempts=2, initial_delay_ms=10)
        executor = ReliableTaskExecutor(retry_policy=policy)
        
        success, result, error = await executor.execute_task(fail_task)
        
        assert success is False
        assert result is None
        assert error is not None
    
    @pytest.mark.asyncio
    async def test_execute_with_recovery(self):
        """Test task execution with recovery."""
        attempt_count = 0
        
        async def task():
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count < 2:
                raise Exception("First attempt fails")
            return "success"
        
        policy = RetryPolicy(max_attempts=3, initial_delay_ms=10)
        executor = ReliableTaskExecutor(retry_policy=policy)
        
        success, result, error = await executor.execute_task(
            task,
            recovery_actions=[RecoveryAction.RETRY]
        )
        
        assert success is True
    
    def test_get_status(self):
        """Test getting executor status."""
        executor = ReliableTaskExecutor()
        
        status = executor.get_status()
        
        assert "attempts_made" in status
        assert "successful_recoveries" in status
        assert "failed_recoveries" in status
        assert "total_recovery_attempts" in status


class TestRetryEdgeCases:
    """Tests for edge cases."""
    
    def test_policy_with_zero_attempts(self):
        """Test policy with unreasonable values."""
        policy = RetryPolicy(max_attempts=0)
        
        assert policy.max_attempts == 0
        assert policy.get_delay_ms(0) >= 0
    
    def test_policy_with_negative_delay(self):
        """Test policy with negative initial delay."""
        policy = RetryPolicy(initial_delay_ms=-100)
        
        # Should handle gracefully
        delay = policy.get_delay_ms(0)
        assert isinstance(delay, int)
    
    @pytest.mark.asyncio
    async def test_retry_with_arguments(self):
        """Test task with arguments."""
        async def task_with_args(a, b, c=None):
            return a + b + (c or 0)
        
        retry = TaskRetry()
        
        success, result, error = await retry.execute_with_retry(
            task_with_args,
            1, 2, c=3
        )
        
        assert success is True
        assert result == 6
