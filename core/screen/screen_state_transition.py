"""Screen State Transition Detector
==================================

Detects and validates state transitions between screens.
"""

import logging
from typing import Optional, Dict, Set, Tuple
from dataclasses import dataclass

from .screen_types import ScreenType

logger = logging.getLogger(__name__)


@dataclass
class StateTransition:
    """Represents a valid state transition."""
    from_state: ScreenType
    to_state: ScreenType
    action: str  # e.g., "click chrome profile", "search"
    confidence: float = 0.8


class ScreenStateTransitionDetector:
    """Detects and validates screen state transitions."""
    
    # Define valid transitions
    VALID_TRANSITIONS = {
        ScreenType.DESKTOP: {
            ScreenType.CHROME_BROWSER,
            ScreenType.CHROME_PROFILE,
            ScreenType.FILE_EXPLORER,
            ScreenType.NOTEPAD,
        },
        ScreenType.CHROME_PROFILE: {
            ScreenType.CHROME_BROWSER,
            ScreenType.CHROME_START,
        },
        ScreenType.CHROME_START: {
            ScreenType.CHROME_BROWSER,
            ScreenType.CHROME_PROFILE,
        },
        ScreenType.CHROME_BROWSER: {
            ScreenType.GOOGLE_HOMEPAGE,
            ScreenType.GOOGLE_SEARCH_RESULTS,
            ScreenType.YOUTUBE_HOME,
            ScreenType.YOUTUBE_VIDEO,
            ScreenType.LOGIN_PAGE,
            ScreenType.ERROR_PAGE,
            ScreenType.BLANK_PAGE,
            ScreenType.CHROME_BROWSER,  # Stay on same page
            ScreenType.CHROME_ERROR,
        },
        ScreenType.GOOGLE_HOMEPAGE: {
            ScreenType.GOOGLE_SEARCH_RESULTS,
            ScreenType.CHROME_BROWSER,
        },
        ScreenType.GOOGLE_SEARCH_RESULTS: {
            ScreenType.CHROME_BROWSER,
            ScreenType.GOOGLE_HOMEPAGE,
            ScreenType.GOOGLE_SEARCH_RESULTS,  # Next page
        },
        ScreenType.YOUTUBE_HOME: {
            ScreenType.YOUTUBE_VIDEO,
            ScreenType.CHROME_BROWSER,
        },
        ScreenType.YOUTUBE_VIDEO: {
            ScreenType.YOUTUBE_HOME,
            ScreenType.YOUTUBE_VIDEO,  # Watch related
        },
        ScreenType.LOGIN_PAGE: {
            ScreenType.CHROME_BROWSER,
            ScreenType.ERROR_PAGE,
            ScreenType.LOGIN_PAGE,  # Retry
        },
        ScreenType.ERROR_PAGE: {
            ScreenType.CHROME_BROWSER,
            ScreenType.DESKTOP,
        },
        ScreenType.FILE_EXPLORER: {
            ScreenType.FILE_EXPLORER,  # Navigate folders
            ScreenType.DESKTOP,
            ScreenType.NOTEPAD,
        },
    }
    
    def __init__(self):
        """Initialize transition detector."""
        logger.info("ScreenStateTransitionDetector initialized")
    
    def is_valid_transition(
        self, 
        from_state: ScreenType, 
        to_state: ScreenType
    ) -> bool:
        """Check if transition is valid.
        
        Args:
            from_state: Current screen state
            to_state: Target screen state
            
        Returns:
            True if transition is valid
        """
        if from_state not in self.VALID_TRANSITIONS:
            logger.warning(f"No transitions defined for {from_state}")
            return False
        
        valid_targets = self.VALID_TRANSITIONS[from_state]
        is_valid = to_state in valid_targets
        
        if not is_valid:
            logger.warning(
                f"Invalid transition: {from_state} -> {to_state}"
            )
        
        return is_valid
    
    def get_valid_next_states(self, current_state: ScreenType) -> Set[ScreenType]:
        """Get all valid next states.
        
        Args:
            current_state: Current screen state
            
        Returns:
            Set of valid next states
        """
        return self.VALID_TRANSITIONS.get(
            current_state, 
            set()
        )
    
    def detect_unexpected_transition(
        self,
        from_state: ScreenType,
        to_state: ScreenType
    ) -> bool:
        """Detect if transition is unexpected.
        
        Args:
            from_state: Previous state
            to_state: Current state
            
        Returns:
            True if transition is unexpected (invalid)
        """
        return not self.is_valid_transition(from_state, to_state)
    
    def get_recovery_path(
        self,
        current_state: ScreenType,
        target_state: ScreenType
    ) -> Optional[list]:
        """Get a path from current to target state.
        
        Args:
            current_state: Current screen state
            target_state: Desired screen state
            
        Returns:
            List of states to visit (path) or None
        """
        # Simple BFS path finding
        if current_state == target_state:
            return [current_state]
        
        queue = [(current_state, [current_state])]
        visited = {current_state}
        
        while queue:
            state, path = queue.pop(0)
            
            # Get next possible states
            next_states = self.get_valid_next_states(state)
            
            for next_state in next_states:
                if next_state == target_state:
                    return path + [next_state]
                
                if next_state not in visited:
                    visited.add(next_state)
                    queue.append((next_state, path + [next_state]))
        
        logger.warning(
            f"No path found from {current_state} to {target_state}"
        )
        return None
    
    def suggest_action_for_state(self, state: ScreenType) -> str:
        """Suggest appropriate action for current state.
        
        Args:
            state: Current screen state
            
        Returns:
            Suggested action description
        """
        suggestions = {
            ScreenType.CHROME_PROFILE: "Select a Chrome user profile",
            ScreenType.CHROME_BROWSER: "Navigate to a website",
            ScreenType.GOOGLE_HOMEPAGE: "Enter search query",
            ScreenType.GOOGLE_SEARCH_RESULTS: "Click a search result",
            ScreenType.YOUTUBE_HOME: "Search or browse videos",
            ScreenType.LOGIN_PAGE: "Enter credentials",
            ScreenType.ERROR_PAGE: "Go back or reload",
            ScreenType.DESKTOP: "Open an application",
            ScreenType.FILE_EXPLORER: "Navigate or open files",
        }
        
        return suggestions.get(state, "Unknown state")
