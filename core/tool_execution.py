# Adapted from OpenClaw (https://github.com/openclaw/openclaw)
# Production-ready tool execution pipeline

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional, Dict, List
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class ToolResultStatus(Enum):
    """Tool execution status"""
    SUCCESS = "success"
    FAILURE = "failure"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


@dataclass
class ToolCall:
    """Represents a tool invocation"""
    tool_name: str
    input_params: Dict[str, Any]
    tool_use_id: Optional[str] = None


@dataclass
class ToolResult:
    """Exact adaptation of OpenClaw's tool result tracking"""
    tool_name: str
    tool_use_id: Optional[str] = None
    input_params: Dict[str, Any] = field(default_factory=dict)
    output: Optional[str] = None
    status: ToolResultStatus = ToolResultStatus.SUCCESS
    duration_ms: float = 0.0
    error: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return {
            "tool_name": self.tool_name,
            "tool_use_id": self.tool_use_id,
            "status": self.status.value,
            "output": self.output,
            "duration_ms": self.duration_ms,
            "error": self.error,
        }


class ToolExecutionPipeline:
    """
    Tool execution with before/after hooks
    Exact adaptation from OpenClaw's pi-tool-definition-adapter.ts
    From: src/agents/pi-tool-definition-adapter.ts
    """
    
    def __init__(self, session_key: str):
        self.session_key = session_key
        self.before_call_hooks: List[Callable[[str, Dict], Any]] = []
        self.after_call_hooks: List[Callable[[ToolResult], Any]] = []
        self.max_retries = 3
    
    def add_before_call_hook(self, hook: Callable[[str, Dict], Any]) -> None:
        """Add hook to run before tool execution"""
        self.before_call_hooks.append(hook)
    
    def add_after_call_hook(self, hook: Callable[[ToolResult], Any]) -> None:
        """Add hook to run after tool execution"""
        self.after_call_hooks.append(hook)
    
    async def execute(
        self,
        tool_call: ToolCall,
        execute_fn: Callable[[str, Dict], Any],
        timeout_sec: float = 30.0,
    ) -> ToolResult:
        """
        Execute tool with all hooks and error handling
        Pattern from OpenClaw's tool execution flow
        """
        result = ToolResult(
            tool_name=tool_call.tool_name,
            tool_use_id=tool_call.tool_use_id,
            input_params=tool_call.input_params.copy(),
        )
        
        try:
            # RUN BEFORE-CALL HOOKS
            for hook in self.before_call_hooks:
                try:
                    self._run_hook(hook, tool_call.tool_name, tool_call.input_params)
                except Exception as e:
                    logger.warning(f"Before-call hook error: {e}")
            
            # EXECUTE TOOL
            start_time = time.time()
            try:
                output = await asyncio.wait_for(
                    asyncio.to_thread(execute_fn, tool_call.tool_name, tool_call.input_params),
                    timeout=timeout_sec
                )
                result.output = str(output) if output is not None else ""
                result.status = ToolResultStatus.SUCCESS
                
            except asyncio.TimeoutError:
                result.status = ToolResultStatus.TIMEOUT
                result.error = f"Tool execution timed out after {timeout_sec} seconds"
                logger.warning(f"Tool timeout: {tool_call.tool_name}")
                
            except asyncio.CancelledError:
                result.status = ToolResultStatus.CANCELLED
                result.error = "Tool execution was cancelled"
                logger.info(f"Tool cancelled: {tool_call.tool_name}")
                
            except Exception as e:
                result.status = ToolResultStatus.FAILURE
                result.error = str(e)
                logger.error(f"Tool execution failed: {tool_call.tool_name}", exc_info=True)
            
            finally:
                result.duration_ms = (time.time() - start_time) * 1000
            
            # RUN AFTER-CALL HOOKS
            for hook in self.after_call_hooks:
                try:
                    self._run_hook(hook, result)
                except Exception as e:
                    logger.warning(f"After-call hook error: {e}")
            
            return result
        
        except Exception as e:
            result.status = ToolResultStatus.FAILURE
            result.error = str(e)
            logger.error(f"Tool pipeline error: {tool_call.tool_name}", exc_info=True)
            return result
    
    @staticmethod
    def _run_hook(hook: Callable, *args) -> None:
        """Run a hook function"""
        if asyncio.iscoroutinefunction(hook):
            # Would need to be awaited in async context
            raise RuntimeError("Hooks must be sync")
        hook(*args)
    
    async def execute_with_retry(
        self,
        tool_call: ToolCall,
        execute_fn: Callable[[str, Dict], Any],
        timeout_sec: float = 30.0,
        retry_count: int = 0,
    ) -> ToolResult:
        """Execute tool with automatic retry on failure"""
        result = await self.execute(
            tool_call,
            execute_fn,
            timeout_sec
        )
        
        # Retry on non-timeout failures
        if result.status == ToolResultStatus.FAILURE and retry_count < self.max_retries:
            logger.info(f"Retrying tool {tool_call.tool_name} (attempt {retry_count + 1})")
            await asyncio.sleep(0.5 * (2 ** retry_count))  # Exponential backoff
            return await self.execute_with_retry(
                tool_call,
                execute_fn,
                timeout_sec,
                retry_count + 1
            )
        
        return result


# Example tool registry matching OpenClaw's pattern
class ToolRegistry:
    """Registry of available tools"""
    
    def __init__(self):
        self.tools: Dict[str, Callable] = {}
    
    def register(self, name: str, tool_fn: Callable) -> None:
        """Register a tool function"""
        self.tools[name] = tool_fn
    
    def get(self, name: str) -> Optional[Callable]:
        """Get tool function by name"""
        return self.tools.get(name)
    
    def list_tools(self) -> List[str]:
        """List all registered tools"""
        return list(self.tools.keys())


# Example usage
async def example():
    # Define tools
    def execute_bash(tool_name: str, params: Dict) -> str:
        """Execute bash command"""
        command = params.get("command", "")
        # In reality, would use subprocess
        return f"Output of: {command}"
    
    def execute_read_file(tool_name: str, params: Dict) -> str:
        """Read file"""
        path = params.get("path", "")
        return f"Contents of: {path}"
    
    # Create registry
    registry = ToolRegistry()
    registry.register("bash", execute_bash)
    registry.register("read_file", execute_read_file)
    
    # Create pipeline
    pipeline = ToolExecutionPipeline(session_key="session-123")
    
    # Add logging hooks
    def log_before(tool: str, params: Dict):
        logger.info(f"Executing tool: {tool} with {params}")
    
    def log_after(result: ToolResult):
        logger.info(f"Tool completed: {result.tool_name} status={result.status.value} duration={result.duration_ms:.1f}ms")
    
    pipeline.add_before_call_hook(log_before)
    pipeline.add_after_call_hook(log_after)
    
    # Execute
    tool_call = ToolCall(
        tool_name="bash",
        input_params={"command": "ls -la"},
        tool_use_id="tool-1"
    )
    
    result = await pipeline.execute(
        tool_call,
        registry.get("bash"),
        timeout_sec=5.0
    )
    
    print(f"Result: {result.to_dict()}")
