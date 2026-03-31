"""Advanced Decision Router - The Critical Decision Layer

This is the core improvement that prevents the "type entire instruction" problem.

The router implements the proper decision pipeline:
  User Command → Intent Classification → Decision Logic → Route to Handler

Key Decision Rule (Prevents Wrong Typing):
  IF intent != TYPE_TEXT:
      Use workflow template or smart planner
  ELSE:
      Direct text typing

This ensures that "Open Edge and search BTS V" doesn't get typed verbatim.
"""

from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass
import logging
from enum import Enum

from core.intent_classifier import IntentClassifier, IntentType, IntentResult, get_workflow_template

logger = logging.getLogger(__name__)


class ExecutionStrategy(Enum):
    """How to execute a task based on intent"""
    USE_TEMPLATE = "use_template"          # Use pre-built workflow
    CALL_PLANNER = "call_planner"          # Ask planner agent to create plan
    DIRECT_EXECUTION = "direct_execution"  # Execute directly (simple tasks)
    HYBRID = "hybrid"                      # Mix template + planning
    MANUAL_PLANNING = "manual_planning"    # Fallback, needs human review


@dataclass
class DecisionResult:
    """Result of routing decision"""
    intent: IntentType
    confidence: float
    strategy: ExecutionStrategy
    plan: List[Dict[str, Any]]
    reasoning: str
    requires_planning: bool
    estimated_steps: int


class DecisionRouter:
    """
    Routes commands through proper decision pipeline.
    
    This is what makes the system behave like a real agent instead of
    a macro recorder that types instructions.
    """
    
    def __init__(self):
        self.classifier = IntentClassifier()
        self.logger = logger
        
        # Strategy decision matrix
        self.strategy_map = {
            IntentType.OPEN_APP: ExecutionStrategy.USE_TEMPLATE,
            IntentType.WEB_SEARCH: ExecutionStrategy.USE_TEMPLATE,
            IntentType.OPEN_URL: ExecutionStrategy.USE_TEMPLATE,
            IntentType.CLICK: ExecutionStrategy.DIRECT_EXECUTION,
            IntentType.SCROLL: ExecutionStrategy.DIRECT_EXECUTION,
            IntentType.TYPE_TEXT: ExecutionStrategy.DIRECT_EXECUTION,
            IntentType.SYSTEM: ExecutionStrategy.DIRECT_EXECUTION,
            IntentType.FILE_OPEN: ExecutionStrategy.CALL_PLANNER,
            IntentType.FILE_SAVE: ExecutionStrategy.CALL_PLANNER,
            IntentType.NAVIGATION: ExecutionStrategy.CALL_PLANNER,
            IntentType.FORM_FILL: ExecutionStrategy.HYBRID,
            IntentType.CUSTOM_WORKFLOW: ExecutionStrategy.USE_TEMPLATE,
            IntentType.UNKNOWN: ExecutionStrategy.CALL_PLANNER,
        }
    
    def decide(self, command: str) -> DecisionResult:
        """
        Make routing decision for a command.
        
        This is the gateway that prevents incorrect execution.
        
        Args:
            command: User's natural language command
            
        Returns:
            DecisionResult with routing strategy and execution plan
        """
        
        # Step 1: Classify Intent
        intent_result = self._classify_intent(command)
        
        # Step 2: Decide Execution Strategy
        strategy = self._select_strategy(intent_result)
        
        # Step 3: Build Execution Plan
        plan = self._build_plan(intent_result, strategy, command)
        
        # Step 4: Validate Decision
        self._validate_decision(intent_result, strategy, plan)
        
        # Create and return decision
        return DecisionResult(
            intent=intent_result.intent,
            confidence=intent_result.confidence,
            strategy=strategy,
            plan=plan,
            reasoning=self._create_reasoning(intent_result, strategy),
            requires_planning=strategy in (
                ExecutionStrategy.CALL_PLANNER,
                ExecutionStrategy.HYBRID
            ),
            estimated_steps=len(plan)
        )
    
    def _classify_intent(self, command: str) -> IntentResult:
        """Classify the command intent"""
        self.logger.info(f"Classifying intent for: {command}")
        result = self.classifier.classify(command)
        self.logger.info(f"Intent: {result.intent.value}, Confidence: {result.confidence}")
        return result
    
    def _select_strategy(self, intent_result: IntentResult) -> ExecutionStrategy:
        """Select execution strategy based on intent"""
        # High-confidence intents with templates → use template
        if (intent_result.confidence >= 0.85 and
            intent_result.intent in self.strategy_map and
            self.strategy_map[intent_result.intent] == ExecutionStrategy.USE_TEMPLATE):
            return ExecutionStrategy.USE_TEMPLATE
        
        # Medium-confidence or complex → use planner
        if intent_result.confidence < 0.7:
            return ExecutionStrategy.CALL_PLANNER
        
        # Default strategy for intent type
        return self.strategy_map.get(intent_result.intent, ExecutionStrategy.CALL_PLANNER)
    
    def _build_plan(self, intent_result: IntentResult, strategy: ExecutionStrategy,
                    command: str) -> List[Dict[str, Any]]:
        """Build execution plan based on strategy"""
        
        if strategy == ExecutionStrategy.USE_TEMPLATE:
            return self._build_from_template(intent_result)
        
        elif strategy == ExecutionStrategy.DIRECT_EXECUTION:
            return self._build_direct_plan(intent_result)
        
        elif strategy == ExecutionStrategy.CALL_PLANNER:
            return self._build_planning_placeholder(command)
        
        elif strategy == ExecutionStrategy.HYBRID:
            template_plan = self._build_from_template(intent_result)
            planning_steps = self._build_planning_placeholder(command)
            return template_plan + planning_steps
        
        else:  # MANUAL_PLANNING
            return self._build_planning_placeholder(command)
    
    def _build_from_template(self, intent_result: IntentResult) -> List[Dict[str, Any]]:
        """Build plan from workflow template"""
        template_name = intent_result.suggested_workflow
        if not template_name:
            return self._build_planning_placeholder("Unknown workflow")
        
        template = get_workflow_template(template_name)
        if not template:
            self.logger.warning(f"Template not found: {template_name}")
            return self._build_planning_placeholder("Unknown workflow")
        
        # Substitute parameters into template
        plan = []
        for step in template:
            step_copy = step.copy()
            
            # Replace parameter placeholders
            if isinstance(step_copy.get('value'), str):
                for param_name, param_value in intent_result.parameters.items():
                    placeholder = f"{{{param_name}}}"
                    if placeholder in str(step_copy['value']):
                        step_copy['value'] = str(step_copy['value']).replace(
                            placeholder, str(param_value)
                        )
            
            plan.append(step_copy)
        
        self.logger.info(f"Built plan from template {template_name}: {len(plan)} steps")
        return plan
    
    def _build_direct_plan(self, intent_result: IntentResult) -> List[Dict[str, Any]]:
        """Build plan for direct execution"""
        intent = intent_result.intent
        params = intent_result.parameters
        
        if intent == IntentType.CLICK:
            return [{
                'step': 1,
                'action': 'click',
                'value': params.get('element', 'unknown'),
                'description': f"Click {params.get('element')}"
            }]
        
        elif intent == IntentType.SCROLL:
            return [{
                'step': 1,
                'action': 'scroll',
                'value': f"{params.get('direction', 'down')}:{params.get('amount', 5)}",
                'description': f"Scroll {params.get('direction', 'down')} {params.get('amount', 5)} units"
            }]
        
        elif intent == IntentType.TYPE_TEXT:
            return [{
                'step': 1,
                'action': 'type',
                'value': params.get('text', ''),
                'description': "Type text"
            }]
        
        elif intent == IntentType.SYSTEM:
            return [{
                'step': 1,
                'action': 'system_command',
                'value': params.get('command', ''),
                'description': f"Execute system command: {params.get('command')}"
            }]
        
        else:
            return self._build_planning_placeholder("Direct execution type not supported")
    
    def _build_planning_placeholder(self, reason: str = "") -> List[Dict[str, Any]]:
        """Build placeholder plan requesting planner"""
        return [{
            'step': 1,
            'action': 'plan',
            'value': reason,
            'description': f"Requires planning: {reason}"
        }]
    
    def _validate_decision(self, intent_result: IntentResult, strategy: ExecutionStrategy,
                          plan: List[Dict[str, Any]]) -> None:
        """Validate routing decision"""
        
        # Check for inconsistencies
        if not plan:
            self.logger.warning(f"Empty plan for intent {intent_result.intent.value}")
        
        if strategy == ExecutionStrategy.USE_TEMPLATE and len(plan) > 15:
            self.logger.warning(f"Template plan has {len(plan)} steps (expected <15)")
        
        self.logger.debug(f"Validation passed: {strategy.value}, {len(plan)} steps")
    
    def _create_reasoning(self, intent_result: IntentResult,
                         strategy: ExecutionStrategy) -> str:
        """Create human-readable reasoning"""
        return (
            f"Intent: {intent_result.intent.value} "
            f"(confidence: {intent_result.confidence:.0%}). "
            f"Strategy: {strategy.value}. "
            f"Reason: {intent_result.reasoning}"
        )


class ProtectedExecutor:
    """
    Wrapper that prevents dangerous execution patterns.
    
    Key Protection: NEVER type instruction if intent is not TYPE_TEXT
    This is the critical fix that stops "type entire instruction" problem.
    """
    
    def __init__(self, executor):
        self.executor = executor
        self.router = DecisionRouter()
        self.logger = logger
    
    def execute_task(self, command: str) -> Dict[str, Any]:
        """
        Execute task with decision routing and protection.
        
        Args:
            command: User command
            
        Returns:
            Execution result
        """
        
        # Step 1: Get routing decision
        decision = self.router.decide(command)
        self.logger.info(f"Decision: {decision.strategy.value}")
        self.logger.info(f"Reasoning: {decision.reasoning}")
        
        # Step 2: CRITICAL PROTECTION - Check intent before typing
        if self._is_risky_command(decision):
            self.logger.warning(
                f"Risky command detected! Intent: {decision.intent.value}. "
                f"Would NOT type entire instruction. Using template/planner instead."
            )
            return {
                'status': 'protected',
                'reason': 'Intent indicates not to type entire instruction',
                'intent': decision.intent.value,
                'decision': decision.strategy.value
            }
        
        # Step 3: Execute plan
        result = self._execute_plan(decision.plan, command)
        
        return {
            'status': 'success',
            'intent': decision.intent.value,
            'strategy': decision.strategy.value,
            'steps_executed': len(decision.plan),
            'result': result
        }
    
    def _is_risky_command(self, decision: DecisionResult) -> bool:
        """
        Check if executing the entire instruction as typed would be wrong.
        
        Returns True if we should NOT just type the command.
        """
        risky_intents = [
            IntentType.OPEN_APP,
            IntentType.WEB_SEARCH,
            IntentType.OPEN_URL,
            IntentType.NAVIGATION,
            IntentType.FORM_FILL,
            IntentType.FILE_OPEN,
            IntentType.FILE_SAVE,
        ]
        
        return decision.intent in risky_intents
    
    def _execute_plan(self, plan: List[Dict[str, Any]], command: str) -> Dict[str, Any]:
        """Execute the plan steps"""
        results = []
        
        for step in plan:
            try:
                if step['action'] == 'plan':
                    # Requires planner - call it
                    result = self._call_planner(command)
                else:
                    # Execute step directly
                    result = self.executor.execute_step(step)
                
                results.append(result)
                self.logger.info(f"Step {step.get('step')}: {step.get('description')} - OK")
                
            except Exception as e:
                self.logger.error(f"Step {step.get('step')} failed: {e}")
                results.append({'error': str(e)})
        
        return {'steps': results}
    
    def _call_planner(self, command: str) -> Dict[str, Any]:
        """Call the planner agent for complex tasks"""
        # This will be connected to the actual planner agent
        self.logger.info(f"Requesting planner for: {command}")
        return {'action': 'planning_required', 'command': command}
