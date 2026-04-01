# Adapted from OpenClaw (https://github.com/openclaw/openclaw)
# Production-ready session lifecycle state management

from dataclasses import dataclass, field
from typing import Optional
from enum import Enum
import time
import logging

logger = logging.getLogger(__name__)


class SessionStatus(str, Enum):
    """Exact adaptation of OpenClaw's SessionRunStatus"""
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    KILLED = "killed"
    TIMEOUT = "timeout"


class LifecyclePhase(str, Enum):
    """Phases from OpenClaw's session-lifecycle-state.ts"""
    START = "start"
    END = "end"
    ERROR = "error"


@dataclass
class LifecycleEvent:
    """Exact adaptation of OpenClaw's LifecycleEventLike"""
    ts: int  # timestamp in milliseconds
    phase: Optional[LifecyclePhase] = None
    started_at: Optional[int] = None
    ended_at: Optional[int] = None
    aborted: bool = False
    stop_reason: Optional[str] = None  # "aborted" or other


@dataclass
class SessionLifecycleSnapshot:
    """Exact adaptation of GatewaySessionLifecycleSnapshot"""
    updated_at: Optional[int] = None
    status: Optional[SessionStatus] = None
    started_at: Optional[int] = None
    ended_at: Optional[int] = None
    runtime_ms: Optional[int] = None
    aborted_last_run: bool = False


class SessionLifecycleStateManager:
    """
    Exact adaptation of OpenClaw's deriveGatewaySessionLifecycleSnapshot logic
    From: src/gateway/session-lifecycle-state.ts
    """
    
    @staticmethod
    def is_finite_timestamp(value) -> bool:
        """Check if value is a valid finite timestamp"""
        return isinstance(value, (int, float)) and value > 0 and value == value  # not NaN
    
    @staticmethod
    def resolve_lifecycle_phase(event: LifecycleEvent) -> Optional[LifecyclePhase]:
        """Extract phase from event"""
        if event.phase and event.phase in (LifecyclePhase.START, LifecyclePhase.END, LifecyclePhase.ERROR):
            return event.phase
        return None
    
    @staticmethod
    def resolve_terminal_status(event: LifecycleEvent) -> SessionStatus:
        """Determine final session status from lifecycle event"""
        phase = SessionLifecycleStateManager.resolve_lifecycle_phase(event)
        
        if phase == LifecyclePhase.ERROR:
            return SessionStatus.FAILED
        
        if event.stop_reason == "aborted":
            return SessionStatus.KILLED
        
        if event.aborted:
            return SessionStatus.TIMEOUT
        
        return SessionStatus.DONE
    
    @staticmethod
    def resolve_lifecycle_started_at(
        existing_started_at: Optional[int],
        event: LifecycleEvent
    ) -> Optional[int]:
        """Get or infer session start time"""
        if SessionLifecycleStateManager.is_finite_timestamp(event.started_at):
            return event.started_at
        
        if SessionLifecycleStateManager.is_finite_timestamp(existing_started_at):
            return existing_started_at
        
        if SessionLifecycleStateManager.is_finite_timestamp(event.ts):
            return event.ts
        
        return None
    
    @staticmethod
    def resolve_lifecycle_ended_at(event: LifecycleEvent) -> Optional[int]:
        """Get or infer session end time"""
        if SessionLifecycleStateManager.is_finite_timestamp(event.ended_at):
            return event.ended_at
        
        if SessionLifecycleStateManager.is_finite_timestamp(event.ts):
            return event.ts
        
        return None
    
    @staticmethod
    def resolve_runtime_ms(
        started_at: Optional[int],
        ended_at: Optional[int],
        existing_runtime_ms: Optional[int]
    ) -> Optional[int]:
        """Calculate total runtime in milliseconds"""
        if (SessionLifecycleStateManager.is_finite_timestamp(started_at) and
            SessionLifecycleStateManager.is_finite_timestamp(ended_at)):
            return max(0, ended_at - started_at)
        
        if (isinstance(existing_runtime_ms, int) and
            existing_runtime_ms >= 0):
            return existing_runtime_ms
        
        return None
    
    @staticmethod
    def derive_lifecycle_snapshot(
        previous_state: Optional[SessionLifecycleSnapshot],
        event: LifecycleEvent
    ) -> SessionLifecycleSnapshot:
        """
        Exact adaptation of OpenClaw's deriveGatewaySessionLifecycleSnapshot
        Updates session state based on lifecycle event
        """
        phase = SessionLifecycleStateManager.resolve_lifecycle_phase(event)
        if not phase:
            return SessionLifecycleSnapshot()
        
        existing = previous_state or SessionLifecycleSnapshot()
        
        if phase == LifecyclePhase.START:
            started_at = SessionLifecycleStateManager.resolve_lifecycle_started_at(
                existing.started_at, event
            )
            updated_at = started_at or existing.updated_at
            
            return SessionLifecycleSnapshot(
                updated_at=updated_at,
                status=SessionStatus.RUNNING,
                started_at=started_at,
                ended_at=None,
                runtime_ms=None,
                aborted_last_run=False
            )
        
        # END or ERROR phase
        started_at = SessionLifecycleStateManager.resolve_lifecycle_started_at(
            existing.started_at, event
        )
        ended_at = SessionLifecycleStateManager.resolve_lifecycle_ended_at(event)
        updated_at = ended_at or existing.updated_at
        runtime_ms = SessionLifecycleStateManager.resolve_runtime_ms(
            started_at, ended_at, existing.runtime_ms
        )
        
        return SessionLifecycleSnapshot(
            updated_at=updated_at,
            status=SessionLifecycleStateManager.resolve_terminal_status(event),
            started_at=started_at,
            ended_at=ended_at,
            runtime_ms=runtime_ms,
            aborted_last_run=event.aborted
        )
