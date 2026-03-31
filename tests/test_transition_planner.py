"""Tests for Screen Transition Planner
======================================

Tests transition planning, pathfinding, and validation.
"""

import pytest
from core.screen.transition_planner import (
    TransitionType,
    ScreenTransition,
    TransitionGraph,
    TransitionPlanner,
    TransitionValidator
)


class TestTransitionType:
    """Tests for TransitionType enum."""
    
    def test_transition_type_values(self):
        """Test transition type values."""
        assert TransitionType.DIRECT.value == "direct"
        assert TransitionType.BROWSER_BACK.value == "browser_back"
        assert TransitionType.ESCAPE.value == "escape"


class TestScreenTransition:
    """Tests for ScreenTransition dataclass."""
    
    def test_transition_creation(self):
        """Test creating a transition."""
        transition = ScreenTransition(
            from_screen="DESKTOP",
            to_screen="CHROME_BROWSER",
            transition_type=TransitionType.APPLICATION,
            action_description="Launch Chrome"
        )
        
        assert transition.from_screen == "DESKTOP"
        assert transition.to_screen == "CHROME_BROWSER"
        assert transition.cost == 1.0
        assert transition.preconditions == []
    
    def test_transition_with_conditions(self):
        """Test transition with conditions."""
        transition = ScreenTransition(
            from_screen="LOGIN",
            to_screen="BROWSER",
            transition_type=TransitionType.CLICK_ELEMENT,
            action_description="Click login button",
            preconditions=["form_filled", "credentials_valid"],
            postconditions=["authenticated"]
        )
        
        assert len(transition.preconditions) == 2
        assert "authenticated" in transition.postconditions
    
    def test_transition_with_cost(self):
        """Test transition with custom cost."""
        transition = ScreenTransition(
            from_screen="A",
            to_screen="B",
            transition_type=TransitionType.DIRECT,
            action_description="Go to B",
            cost=5.0
        )
        
        assert transition.cost == 5.0


class TestTransitionGraph:
    """Tests for TransitionGraph."""
    
    def test_graph_initialization(self):
        """Test graph initialization."""
        graph = TransitionGraph()
        
        assert graph.transitions == {}
        assert graph.states == set()
    
    def test_add_transition(self):
        """Test adding transition to graph."""
        graph = TransitionGraph()
        transition = ScreenTransition(
            from_screen="A",
            to_screen="B",
            transition_type=TransitionType.DIRECT,
            action_description="A to B"
        )
        
        graph.add_transition(transition)
        
        assert "A" in graph.states
        assert "B" in graph.states
        assert len(graph.transitions["A"]) == 1
    
    def test_add_multiple_transitions(self):
        """Test adding multiple transitions."""
        graph = TransitionGraph()
        
        graph.add_transition(ScreenTransition("A", "B", TransitionType.DIRECT, "A->B"))
        graph.add_transition(ScreenTransition("A", "C", TransitionType.DIRECT, "A->C"))
        graph.add_transition(ScreenTransition("B", "C", TransitionType.DIRECT, "B->C"))
        
        assert len(graph.transitions["A"]) == 2
        assert len(graph.transitions["B"]) == 1
    
    def test_get_transitions_from(self):
        """Test getting transitions from state."""
        graph = TransitionGraph()
        
        t1 = ScreenTransition("A", "B", TransitionType.DIRECT, "A->B")
        t2 = ScreenTransition("A", "C", TransitionType.DIRECT, "A->C")
        
        graph.add_transition(t1)
        graph.add_transition(t2)
        
        transitions = graph.get_transitions_from("A")
        
        assert len(transitions) == 2
        assert t1 in transitions
        assert t2 in transitions
    
    def test_get_all_states(self):
        """Test getting all states."""
        graph = TransitionGraph()
        
        graph.add_transition(ScreenTransition("A", "B", TransitionType.DIRECT, ""))
        graph.add_transition(ScreenTransition("B", "C", TransitionType.DIRECT, ""))
        
        states = graph.get_all_states()
        
        assert states == {"A", "B", "C"}


class TestTransitionPlanner:
    """Tests for TransitionPlanner."""
    
    def test_planner_initialization(self):
        """Test planner initialization."""
        planner = TransitionPlanner()
        
        assert planner.graph is not None
        assert len(planner.graph.states) > 0  # Default transitions added
    
    def test_find_path_direct(self):
        """Test finding direct path."""
        planner = TransitionPlanner()
        graph = TransitionGraph()
        
        graph.add_transition(ScreenTransition("A", "B", TransitionType.DIRECT, "A->B"))
        planner.graph = graph
        
        path = planner.find_path("A", "B")
        
        assert path is not None
        assert len(path) == 1
        assert path[0].from_screen == "A"
    
    def test_find_path_multi_step(self):
        """Test finding multi-step path."""
        planner = TransitionPlanner()
        graph = TransitionGraph()
        
        graph.add_transition(ScreenTransition("A", "B", TransitionType.DIRECT, "A->B"))
        graph.add_transition(ScreenTransition("B", "C", TransitionType.DIRECT, "B->C"))
        graph.add_transition(ScreenTransition("C", "D", TransitionType.DIRECT, "C->D"))
        
        planner.graph = graph
        
        path = planner.find_path("A", "D")
        
        assert path is not None
        assert len(path) == 3
    
    def test_find_path_no_route(self):
        """Test finding path when no route exists."""
        planner = TransitionPlanner()
        graph = TransitionGraph()
        
        graph.add_transition(ScreenTransition("A", "B", TransitionType.DIRECT, ""))
        graph.add_transition(ScreenTransition("C", "D", TransitionType.DIRECT, ""))
        
        planner.graph = graph
        
        path = planner.find_path("A", "D")
        
        assert path is None
    
    def test_find_path_same_state(self):
        """Test finding path to same state."""
        planner = TransitionPlanner()
        
        path = planner.find_path("A", "A")
        
        assert path == []
    
    def test_find_cheapest_path(self):
        """Test finding cheapest path."""
        planner = TransitionPlanner()
        graph = TransitionGraph()
        
        # Path 1: A->B->C (cost 3.0)
        graph.add_transition(ScreenTransition("A", "B", TransitionType.DIRECT, "", cost=1.0))
        graph.add_transition(ScreenTransition("B", "C", TransitionType.DIRECT, "", cost=2.0))
        
        # Path 2: A->D->C (cost 5.0)
        graph.add_transition(ScreenTransition("A", "D", TransitionType.DIRECT, "", cost=3.0))
        graph.add_transition(ScreenTransition("D", "C", TransitionType.DIRECT, "", cost=2.0))
        
        planner.graph = graph
        
        result = planner.find_cheapest_path("A", "C")
        
        assert result is not None
        path, cost = result
        assert len(path) == 2
        assert cost == 3.0  # Cheapest path


class TestTransitionValidator:
    """Tests for TransitionValidator."""
    
    def test_validator_initialization(self):
        """Test validator initialization."""
        validator = TransitionValidator()
        
        assert validator.transition_rules == {}
    
    def test_add_rule(self):
        """Test adding validation rule."""
        validator = TransitionValidator()
        
        def rule(context):
            return True
        
        validator.add_rule("A", "B", rule)
        
        assert "A->B" in validator.transition_rules
    
    @pytest.mark.asyncio
    async def test_validate_transition_no_rule(self):
        """Test validating transition with no rule."""
        validator = TransitionValidator()
        transition = ScreenTransition("A", "B", TransitionType.DIRECT, "")
        
        result = await validator.validate_transition(transition)
        
        assert result is True  # No rule means allowed
    
    @pytest.mark.asyncio
    async def test_validate_transition_with_rule_success(self):
        """Test validating transition with passing rule."""
        validator = TransitionValidator()
        
        async def rule(context):
            return True
        
        validator.add_rule("A", "B", rule)
        transition = ScreenTransition("A", "B", TransitionType.DIRECT, "")
        
        result = await validator.validate_transition(transition)
        
        assert result is True
    
    @pytest.mark.asyncio
    async def test_validate_transition_with_rule_failure(self):
        """Test validating transition with failing rule."""
        validator = TransitionValidator()
        
        async def rule(context):
            return False
        
        validator.add_rule("A", "B", rule)
        transition = ScreenTransition("A", "B", TransitionType.DIRECT, "")
        
        result = await validator.validate_transition(transition)
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_validate_path(self):
        """Test validating entire path."""
        validator = TransitionValidator()
        
        async def rule(context):
            return True
        
        validator.add_rule("A", "B", rule)
        validator.add_rule("B", "C", rule)
        
        path = [
            ScreenTransition("A", "B", TransitionType.DIRECT, ""),
            ScreenTransition("B", "C", TransitionType.DIRECT, ""),
        ]
        
        result = await validator.validate_path(path)
        
        assert result is True


class TestTransitionEdgeCases:
    """Tests for edge cases."""
    
    def test_cyclic_transitions(self):
        """Test handling cyclic transitions."""
        planner = TransitionPlanner()
        graph = TransitionGraph()
        
        graph.add_transition(ScreenTransition("A", "B", TransitionType.DIRECT, ""))
        graph.add_transition(ScreenTransition("B", "C", TransitionType.DIRECT, ""))
        graph.add_transition(ScreenTransition("C", "A", TransitionType.DIRECT, ""))
        
        planner.graph = graph
        
        path = planner.find_path("A", "C")
        
        assert path is not None
        assert len(path) == 2
    
    def test_self_loop_transition(self):
        """Test self-loop transition."""
        planner = TransitionPlanner()
        graph = TransitionGraph()
        
        graph.add_transition(ScreenTransition("A", "A", TransitionType.DIRECT, ""))
        
        planner.graph = graph
        
        # Same state should return empty path
        path = planner.find_path("A", "A")
        
        assert path == []
    
    def test_large_graph(self):
        """Test with large transition graph."""
        planner = TransitionPlanner()
        graph = TransitionGraph()
        
        # Create chain of 100 states
        for i in range(99):
            graph.add_transition(
                ScreenTransition(f"S{i}", f"S{i+1}", TransitionType.DIRECT, "")
            )
        
        planner.graph = graph
        
        path = planner.find_path("S0", "S99")
        
        assert path is not None
        assert len(path) == 99
