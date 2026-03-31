"""
Router Service — Unified request handling with intelligent routing.

This service integrates the fast Router (two-tier classification) with
existing agents (vision, browser, OS control, orchestrator).

Flow:
1. User request comes in
2. Router classifies WITHOUT screenshot (fast)
3. Based on classification, dispatch to appropriate agent
4. Orchestrator is used as sophisticated fallback
"""

import logging
from typing import Any, Dict, Optional

from core.router import Router
from utils.ollama_client import OllamaClient

logger = logging.getLogger(__name__)


class RouterService:
    """
    Unified service that routes requests intelligently.
    
    Uses the Router for fast classification, then dispatches to
    appropriate handlers (direct response, vision, browser, os control, orchestrator).
    """

    def __init__(
        self,
        config: dict,
        orchestrator: Optional[Any] = None,
        ai_layer: Optional[Any] = None,
    ):
        """
        Initialize the RouterService.

        Args:
            config: Configuration dictionary from settings.yaml
            orchestrator: Optional Orchestrator instance (for complex tasks)
            ai_layer: Optional AILayer instance (alternative to orchestrator)
        """
        self.config = config
        self.orchestrator = orchestrator
        self.ai_layer = ai_layer
        
        # Initialize Ollama client and Router
        self.ollama = OllamaClient(config)
        self.router = Router(self.ollama)
        
        # Counters
        self.total_tasks_handled = 0
        self.tasks_by_route = {
            "direct_response": 0,
            "invoke_vision": 0,
            "invoke_browser": 0,
            "invoke_os_control": 0,
            "invoke_orchestrator": 0,
        }

    def handle_task(self, task: str) -> Dict[str, Any]:
        """
        Handle a user task by routing intelligently.

        Args:
            task: The user's task description.

        Returns:
            Dict with keys:
                - success: bool
                - action: which route was taken
                - result: the outcome
                - response: text response to user
        """
        logger.info(f"[ROUTER SERVICE] Handling task: {task[:60]}...")
        self.total_tasks_handled += 1
        
        try:
            # Step 1: Fast routing (no screenshot)
            route_result = self.router.route(task)
            action = route_result["action"]
            confidence = route_result["confidence"]
            
            # Increment counter
            self.tasks_by_route[action] = self.tasks_by_route.get(action, 0) + 1
            
            # Step 2: Dispatch based on routing decision
            logger.info(
                f"[ROUTER SERVICE] Routing to '{action}' "
                f"(confidence={confidence:.2f})"
            )
            
            if action == "direct_response":
                return self._handle_direct_response(task)
            elif action == "invoke_vision":
                return self._handle_vision(task)
            elif action == "invoke_browser":
                return self._handle_browser(task)
            elif action == "invoke_os_control":
                return self._handle_os_control(task)
            else:  # invoke_orchestrator or unknown
                return self._handle_orchestrator(task)
                
        except Exception as e:
            logger.error(f"[ROUTER SERVICE] Error handling task: {e}", exc_info=True)
            return {
                "success": False,
                "action": "error",
                "result": None,
                "response": f"Error processing task: {str(e)}",
                "error": str(e),
            }

    def _handle_direct_response(self, task: str) -> Dict[str, Any]:
        """
        Handle simple Q&A that requires no computer action.

        Just prompt llama3 for a direct answer.
        """
        logger.info("[ROUTER SERVICE] → Handling as direct Q&A")
        
        prompt = f"""You are a helpful AI assistant running entirely on the user's computer.
The user has a question that doesn't require any actions on their computer.

User's question:
{task}

Provide a clear, concise answer."""

        response = self.ollama.generate(
            model=self.ollama.text_model,  # llama3
            prompt=prompt,
            temperature=0.7,
            max_tokens=300,
        )
        
        return {
            "success": True,
            "action": "direct_response",
            "result": response,
            "response": response,
        }

    def _handle_vision(self, task: str) -> Dict[str, Any]:
        """
        Handle tasks that require screen understanding.

        Delegates to vision_agent (visual element finding, GUI interaction).
        """
        logger.info("[ROUTER SERVICE] → Delegating to Vision Agent")
        
        # Use existing vision agent from orchestrator
        if not self.orchestrator and not self.ai_layer:
            return {
                "success": False,
                "action": "invoke_vision",
                "result": None,
                "response": "Vision agent not available. Falling back to orchestrator.",
                "error": "No orchestrator/ai_layer configured",
            }
        
        # Try to use vision agent directly if available
        try:
            if self.orchestrator:
                result = self.orchestrator.vision.execute_task(task)
                return {
                    "success": result.get("success", False),
                    "action": "invoke_vision",
                    "result": result,
                    "response": result.get("output", "Vision task completed."),
                }
            elif self.ai_layer:
                # AILayer's vision agent
                result = self.ai_layer.orchestrator.vision.execute_task(task)
                return {
                    "success": result.get("success", False),
                    "action": "invoke_vision",
                    "result": result,
                    "response": result.get("output", "Vision task completed."),
                }
        except Exception as e:
            logger.warning(f"[ROUTER SERVICE] Vision agent error: {e}")
            # Fall back to orchestrator
            return self._handle_orchestrator(task)

    def _handle_browser(self, task: str) -> Dict[str, Any]:
        """
        Handle web automation tasks.

        Could delegate to browser_agent (Playwright), but for now falls back to orchestrator.
        """
        logger.info("[ROUTER SERVICE] → Delegating to Browser/Orchestrator")
        
        # For now, use orchestrator which has browser capabilities
        # In future, could route to dedicated browser_agent
        return self._handle_orchestrator(f"Browser task: {task}")

    def _handle_os_control(self, task: str) -> Dict[str, Any]:
        """
        Handle OS-level tasks (file operations, app launching, etc).

        Could delegate to os_control modules directly, but falls back to orchestrator for now.
        """
        logger.info("[ROUTER SERVICE] → Delegating to OS Control/Orchestrator")
        
        # For now, use orchestrator which has full OS control
        # In future, could route to dedicated app/file managers
        return self._handle_orchestrator(f"OS task: {task}")

    def _handle_orchestrator(self, task: str) -> Dict[str, Any]:
        """
        Handle complex multi-step tasks using full orchestrator.

        This is the sophisticated fallback with planning, execution, validation.
        """
        logger.info("[ROUTER SERVICE] → Using full Orchestrator (planning/execution loop)")
        
        if not self.orchestrator and not self.ai_layer:
            return {
                "success": False,
                "action": "invoke_orchestrator",
                "result": None,
                "response": "Orchestrator not available",
                "error": "No orchestrator/ai_layer configured",
            }
        
        try:
            if self.orchestrator:
                result = self.orchestrator.run_task(task)
            else:
                result = self.ai_layer.run_task(task)
            
            return {
                "success": result.get("success", False),
                "action": "invoke_orchestrator",
                "result": result,
                "response": result.get("outcome", "Task completed."),
            }
        except Exception as e:
            logger.error(f"[ROUTER SERVICE] Orchestrator error: {e}")
            return {
                "success": False,
                "action": "invoke_orchestrator",
                "result": None,
                "response": f"Orchestrator failed: {str(e)}",
                "error": str(e),
            }

    def get_stats(self) -> Dict[str, Any]:
        """Return routing service statistics."""
        return {
            "total_tasks_handled": self.total_tasks_handled,
            "tasks_by_route": self.tasks_by_route,
            "router_stats": self.router.get_stats(),
        }
