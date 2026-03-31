"""
Router — Fast Request Classification Layer

Inspired by CLOVIS's two-tier architecture, but using Ollama instead of Gemini.

Instead of expensive screenshot + reasoning, the router classifies requests WITHOUT
screenshots using a lightweight prompt-based approach. This enables fast routing to
specialized agents (vision, browser, OS control, or direct response).

The router answers the question: "Where should this request be handled?"
- direct_response: Simple Q&A, no action needed
- invoke_vision: GUI interaction, screen understanding required
- invoke_browser: Web automation via Playwright
- invoke_os_control: OS/file/app operations
- invoke_orchestrator: Complex multi-step tasks (fallback)
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional

from utils.ollama_client import OllamaClient

logger = logging.getLogger(__name__)


class Router:
    """
    Fast request router that decides where to send each user request.
    
    Uses a lightweight local model (llama3) to classify requests
    WITHOUT screenshot inspection, ensuring fast response times.
    """

    def __init__(self, ollama_client: OllamaClient):
        """
        Initialize the router with an Ollama client.

        Args:
            ollama_client: Connected OllamaClient instance.
        """
        self.ollama = ollama_client
        self.model = self.ollama.text_model  # llama3
        
        # Counters for metrics
        self.route_count = 0
        self.direct_response_count = 0
        self.vision_count = 0
        self.browser_count = 0
        self.os_control_count = 0
        self.orchestrator_count = 0

    def route(self, user_query: str) -> Dict[str, Any]:
        """
        Classify a user request and decide which agent should handle it.

        Args:
            user_query: The user's natural language request.

        Returns:
            Dict with keys:
                - action: One of ["direct_response", "invoke_vision", "invoke_browser", 
                                  "invoke_os_control", "invoke_orchestrator"]
                - task: The original query
                - confidence: 0.0-1.0 confidence score
                - reasoning: Brief explanation
        """
        try:
            result = self._classify_request(user_query)
            self.route_count += 1
            
            # Update counters
            action = result.get("action", "orchestrator")
            if action == "direct_response":
                self.direct_response_count += 1
            elif action == "invoke_vision":
                self.vision_count += 1
            elif action == "invoke_browser":
                self.browser_count += 1
            elif action == "invoke_os_control":
                self.os_control_count += 1
            else:
                self.orchestrator_count += 1
            
            logger.info(
                f"[ROUTER] '{user_query[:60]}...' → {result['action']} "
                f"(confidence={result['confidence']:.2f})"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"[ROUTER] Error classifying request: {e}")
            # Fallback to orchestrator on error
            return {
                "action": "invoke_orchestrator",
                "task": user_query,
                "confidence": 0.5,
                "reasoning": f"Router error: {str(e)}. Falling back to orchestrator."
            }

    def _classify_request(self, user_query: str) -> Dict[str, Any]:
        """
        Internal classification logic using Ollama.

        Args:
            user_query: The user's request.

        Returns:
            Routing decision dictionary.
        """
        # Build routing prompt
        prompt = self._build_routing_prompt(user_query)
        
        # Call llama3 via OllamaClient.generate()
        response = self.ollama.generate(
            prompt=prompt,
            system_prompt=None,
        )
        
        # Parse response
        routing_decision = self._parse_router_response(response)
        
        return routing_decision

    def _build_routing_prompt(self, user_query: str) -> str:
        """
        Build the routing prompt for Ollama.

        Returns:
            Multi-line prompt string.
        """
        system_instructions = """You are a fast request router that classifies user queries.
You do NOT have a screenshot. Decide based on the request text alone.
IMPORTANT: Respond with ONLY a JSON object. No markdown, no extra text."""

        routing_instructions = """# Available Routes
1. direct_response: Simple Q&A that needs no computer action
   - "What is the capital of France?"
   - "How do I cook pasta?"
   - "Tell me about quantum physics"

2. invoke_vision: Requires understanding current screen or GUI interaction
   - "What's on my screen?"
   - "Click the red button"
   - "Find the email from John"
   - "Take a screenshot"

3. invoke_browser: Web automation (browse, search, fill forms)
   - "Open google.com and search for Python"
   - "Go to GitHub and find the pandas repo"
   - "Fill out this form"

4. invoke_os_control: File/app/system operations
   - "Open Notepad"
   - "Create a folder called 'test'"
   - "Close all Chrome windows"

5. invoke_orchestrator: Complex multi-step tasks
   - "Organize my desktop files by date"
   - "Download all images from webpage and resize them"
   - "Send emails to team with meeting notes"

# User Request
{user_query}

# RESPONSE (JSON only - must be valid JSON)
{{
    "action": "direct_response|invoke_vision|invoke_browser|invoke_os_control|invoke_orchestrator",
    "confidence": 0.0-1.0,
    "reasoning": "brief explanation"
}}"""

        return f"{system_instructions}\n\n{routing_instructions.format(user_query=user_query)}"

    def _parse_router_response(self, response: str) -> Dict[str, Any]:
        """
        Parse the router response from Ollama.

        Args:
            response: Raw response string from Ollama.

        Returns:
            Parsed routing decision.
        """
        # Clean response
        response = response.strip()
        
        # Try to extract JSON - handle multi-line JSON
        try:
            # First, try to parse as-is (valid JSON might have newlines)
            if response.startswith("{"):
                # Find the first { and try to match closing }
                brace_count = 0
                end_idx = 0
                for i, char in enumerate(response):
                    if char == "{":
                        brace_count += 1
                    elif char == "}":
                        brace_count -= 1
                        if brace_count == 0:
                            end_idx = i + 1
                            break
                
                if end_idx > 0:
                    json_str = response[:end_idx]
                    data = json.loads(json_str)
                    
                    # Validate and normalize
                    action = data.get("action", "invoke_orchestrator").strip()
                    confidence = float(data.get("confidence", 0.5))
                    reasoning = data.get("reasoning", "")
                    
                    # Ensure valid action
                    valid_actions = [
                        "direct_response",
                        "invoke_vision",
                        "invoke_browser",
                        "invoke_os_control",
                        "invoke_orchestrator"
                    ]
                    if action not in valid_actions:
                        logger.warning(f"[ROUTER] Invalid action: {action}, defaulting to orchestrator")
                        action = "invoke_orchestrator"
                    
                    # Clamp confidence
                    confidence = max(0.0, min(1.0, confidence))
                    
                    return {
                        "action": action,
                        "task": "",
                        "confidence": confidence,
                        "reasoning": reasoning
                    }
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"[ROUTER] JSON parse error: {e}, response was: {response[:100]}")
        
        # Fallback: default to orchestrator on parse failure
        return {
            "action": "invoke_orchestrator",
            "task": "",
            "confidence": 0.3,
            "reasoning": "Could not parse router response"
        }

    def get_stats(self) -> Dict[str, int]:
        """Return routing statistics."""
        return {
            "total_routes": self.route_count,
            "direct_response": self.direct_response_count,
            "vision": self.vision_count,
            "browser": self.browser_count,
            "os_control": self.os_control_count,
            "orchestrator": self.orchestrator_count,
        }
