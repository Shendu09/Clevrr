"""Screen Transition Planner
============================

Plans optimal paths through screen states and manages transitions.
"""

import logging
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class TransitionType(Enum):
    """Types of screen state transitions."""
    DIRECT = "direct"  # Direct navigation
    INTERMEDIATE = "intermediate"  # Requires intermediate steps
    BROWSER_BACK = "browser_back"  # Use browser back button
    ESCAPE = "escape"  # Press escape key
    CLICK_ELEMENT = "click_element"  # Click specific element
    KEYBOARD_SHORTCUT = "keyboard_shortcut"  # Use keyboard shortcut
    APPLICATION = "application"  # Launch/switch application
    RELOAD = "reload"  # Refresh/reload


@dataclass
class ScreenTransition:
    """Represents a single screen state transition."""
    from_screen: str
    to_screen: str
    transition_type: TransitionType
    action_description: str
    cost: float = 1.0  # Cost metric for pathfinding
    preconditions: List[str] = None
    postconditions: List[str] = None
    
    def __post_init__(self):
        if self.preconditions is None:
            self.preconditions = []
        if self.postconditions is None:
            self.postconditions = []


class TransitionGraph:
    """Graph of possible screen transitions."""
    
    def __init__(self):
        """Initialize transition graph."""
        self.transitions: Dict[str, List[ScreenTransition]] = {}
        self.states: set = set()
        logger.info("TransitionGraph initialized")
    
    def add_transition(self, transition: ScreenTransition):
        """Add a transition to the graph.
        
        Args:
            transition: Transition to add
        """
        self.states.add(transition.from_screen)
        self.states.add(transition.to_screen)
        
        if transition.from_screen not in self.transitions:
            self.transitions[transition.from_screen] = []
        
        self.transitions[transition.from_screen].append(transition)
        logger.debug(
            f"Added transition: {transition.from_screen} -> "
            f"{transition.to_screen} ({transition.transition_type.value})"
        )
    
    def get_transitions_from(self, state: str) -> List[ScreenTransition]:
        """Get all transitions from a state.
        
        Args:
            state: State to get transitions from
            
        Returns:
            List of transitions
        """
        return self.transitions.get(state, [])
    
    def get_all_states(self) -> set:
        """Get all states in the graph."""
        return self.states.copy()


class TransitionPlanner:
    """Plans optimal paths between screen states."""
    
    def __init__(self, graph: Optional[TransitionGraph] = None):
        """Initialize planner.
        
        Args:
            graph: Transition graph
        """
        self.graph = graph or TransitionGraph()
        self._setup_default_transitions()
        logger.info("TransitionPlanner initialized")
    
    def _setup_default_transitions(self):
        """Setup default transitions for common scenarios."""
        from core.screen.screen_types import ScreenType
        
        transitions = [
            # Browser navigation
            ScreenTransition(
                ScreenType.GOOGLE_SEARCH_RESULTS.value,
                ScreenType.GOOGLE_HOMEPAGE.value,
                TransitionType.BROWSER_BACK,
                "Click back button",
                cost=1.0
            ),
            ScreenTransition(
                ScreenType.GOOGLE_HOMEPAGE.value,
                ScreenType.CHROME_BROWSER.value,
                TransitionType.BROWSER_BACK,
                "Go back to blank tab",
                cost=1.0
            ),
            
            # Chrome profile selection
            ScreenTransition(
                ScreenType.CHROME_BROWSER.value,
                ScreenType.CHROME_PROFILE.value,
                TransitionType.APPLICATION,
                "Open new Chrome instance",
                cost=2.0
            ),
            
            # Desktop operations
            ScreenTransition(
                ScreenType.DESKTOP.value,
                ScreenType.CHROME_BROWSER.value,
                TransitionType.APPLICATION,
                "Launch Chrome",
                cost=3.0
            ),
            
            # Error recovery
            ScreenTransition(
                ScreenType.ERROR_PAGE.value,
                ScreenType.CHROME_BROWSER.value,
                TransitionType.BROWSER_BACK,
                "Go back from error",
                cost=1.0
            ),
            
            # Login flow
            ScreenTransition(
                ScreenType.LOGIN_PAGE.value,
                ScreenType.CHROME_BROWSER.value,
                TransitionType.DIRECT,
                "Submit login form",
                cost=1.0
            ),
        ]
        
        for transition in transitions:
            self.graph.add_transition(transition)
    
    def find_path(
        self,
        from_state: str,
        to_state: str
    ) -> Optional[List[ScreenTransition]]:
        """Find optimal path between states using BFS.
        
        Args:
            from_state: Starting state
            to_state: Target state
            
        Returns:
            List of transitions forming a path, or None if no path exists
        """
        if from_state == to_state:
            return []
        
        from collections import deque
        
        queue = deque([(from_state, [])])
        visited = {from_state}
        
        while queue:
            current_state, path = queue.popleft()
            
            for transition in self.graph.get_transitions_from(current_state):
                next_state = transition.to_screen
                
                if next_state == to_state:
                    return path + [transition]
                
                if next_state not in visited:
                    visited.add(next_state)
                    queue.append((next_state, path + [transition]))
        
        return None
    
    def find_cheapest_path(
        self,
        from_state: str,
        to_state: str
    ) -> Optional[tuple]:
        """Find cheapest path between states using Dijkstra.
        
        Args:
            from_state: Starting state
            to_state: Target state
            
        Returns:
            Tuple of (path, total_cost) or None
        """
        import heapq
        
        if from_state == to_state:
            return ([], 0.0)
        
        distances = {state: float('inf') for state in self.graph.get_all_states()}
        distances[from_state] = 0.0
        
        parents = {}
        heap = [(0.0, from_state)]
        visited = set()
        
        while heap:
            cost, current_state = heapq.heappop(heap)
            
            if current_state in visited:
                continue
            
            visited.add(current_state)
            
            if current_state == to_state:
                # Reconstruct path
                path = []
                state = to_state
                while state in parents:
                    prev_state, transition = parents[state]
                    path.insert(0, transition)
                    state = prev_state
                return (path, cost)
            
            for transition in self.graph.get_transitions_from(current_state):
                next_state = transition.to_screen
                new_cost = cost + transition.cost
                
                if new_cost < distances[next_state]:
                    distances[next_state] = new_cost
                    parents[next_state] = (current_state, transition)
                    heapq.heappush(heap, (new_cost, next_state))
        
        return None


class TransitionValidator:
    """Validates that transitions are safe and valid."""
    
    def __init__(self):
        """Initialize validator."""
        self.transition_rules: Dict[str, Any] = {}
        logger.info("TransitionValidator initialized")
    
    def add_rule(
        self,
        from_state: str,
        to_state: str,
        rule: callable
    ):
        """Add validation rule.
        
        Args:
            from_state: Starting state
            to_state: Target state
            rule: Validation function
        """
        key = f"{from_state}->{to_state}"
        self.transition_rules[key] = rule
        logger.debug(f"Added validation rule: {key}")
    
    async def validate_transition(
        self,
        transition: ScreenTransition,
        context: Dict[str, Any] = None
    ) -> bool:
        """Validate a transition.
        
        Args:
            transition: Transition to validate
            context: Additional context
            
        Returns:
            True if transition is valid
        """
        context = context or {}
        key = f"{transition.from_screen}->{transition.to_screen}"
        
        if key in self.transition_rules:
            try:
                rule = self.transition_rules[key]
                return await rule(context)
            except Exception as e:
                logger.warning(f"Validation error: {e}")
                return False
        
        # No rule means allowed
        return True
    
    async def validate_path(
        self,
        path: List[ScreenTransition],
        context: Dict[str, Any] = None
    ) -> bool:
        """Validate entire path.
        
        Args:
            path: List of transitions
            context: Additional context
            
        Returns:
            True if entire path is valid
        """
        for transition in path:
            if not await self.validate_transition(transition, context):
                return False
        return True
