# Clevrr Agent Architecture Analysis
## Complete Command Flow to Text Typing

---

## 1. COMMAND FLOW (Step by Step)

### Stage 1: Entry Point → Router Service
```
User Input: "Type my password in the login form"
    ↓
RouterService.handle_task(task_text)
    ├─ Receives natural language command
    ├─ Fast classification (no screenshot)
    └─ Returns routing decision
```

**File**: `core/router_service.py`  
**Method**: `RouterService.handle_task(task: str) → Dict`

### Stage 2: Router Classification
```
Router.route(task_text)
    ├─ Uses llama3 via Ollama (two-tier)
    ├─ No screenshot needed (fast)
    └─ Returns action: [direct_response | invoke_vision | invoke_browser | invoke_os_control | invoke_orchestrator]
```

**File**: `core/router.py`

**Routes decision to**:
- `direct_response` → Q&A that needs no computer action
- `invoke_vision` → Screen analysis tasks
- `invoke_browser` → Browser automation
- `invoke_os_control` → OS-level commands
- `invoke_orchestrator` → Complex multi-step tasks (fallback)

### Stage 3: Orchestrator (for Multi-Step Tasks)
```
Orchestrator.run_task(task_text) → Dict
    ├─ Step 1: SafetyGuard.check_action()
    ├─ Step 2: MemorySystem.find_similar_episodes()
    ├─ Step 3: PlannerAgent.create_plan()
    ├─ Step 4: Execute & Validate Loop
    └─ Step 5: Memory.save_episode()
```

**File**: `agents/orchestrator.py`  
**Key Agents**:
- Safety checker
- Memory system
- Vision agent
- Planner agent
- Executor agent
- Validator agent
- Self-healer

### Stage 4: Planning 
```
PlannerAgent.create_plan(
    task_text,
    screen_description: str,
    memory_context: List[Dict]
) → Dict

    ├─ Uses Ollama llama3 for reasoning
    ├─ Leverages memory for similar tasks
    ├─ Generates JSON plan with steps array
    └─ Returns: {"task": str, "total_steps": int, "steps": [{...}]}
```

**File**: `agents/planner_agent.py`  
**Plan Structure**:
```json
{
  "task": "Type password in login form",
  "total_steps": 2,
  "steps": [
    {
      "step_number": 1,
      "action_type": "click",
      "description": "Click on password field",
      "target": "password input",
      "value": null
    },
    {
      "step_number": 2,
      "action_type": "type",
      "description": "Type the password",
      "target": null,
      "value": "my_password_123",
      "expected_outcome": "Password entered"
    }
  ]
}
```

### Stage 5: Execution Loop
```
for step in plan["steps"]:
    ├─ Safety check (per-step)
    ├─ ExecutorAgent.execute_step(step)
    ├─ ValidatorAgent.validate_step()
    ├─ If fail: SelfHealer.heal()
    └─ Take screenshot for memory
```

**File**: `agents/orchestrator.py` (lines 200-300)

### Stage 6: Executor Agent Router
```
ExecutorAgent.execute_step(step: Dict)
    ├─ Extract: action_type, target, value
    └─ Router by action_type:
        ├─ "click" → click(x, y)
        ├─ "double_click" → double_click(x, y)
        ├─ "right_click" → right_click(x, y)
        ├─ "type" or "type_text" → type_text(value)  ⭐ TEXT HAPPENS HERE
        ├─ "press_key" → press_key(key)
        ├─ "find_and_click" → vision-based click
        ├─ "open_app" → open_app(target)
        ├─ "scroll" → scroll(direction)
        └─ ... [20+ other actions]
```

**File**: `agents/executor_agent.py`  
**Method**: `execute_step(step: dict) → dict`

---

## 2. WHERE TEXT TYPING HAPPENS

### Location: Executor Agent - type_text() Method
**File**: `agents/executor_agent.py`  
**Lines**: ~350-365

```python
def type_text(self, text: str) -> bool:
    """Type text using pyautogui.
    
    Args:
        text: Text to type (from step["value"] or step["target"])
    
    Returns:
        True if typing succeeded
    """
    if not text:
        return False
    try:
        time.sleep(0.5)
        pyautogui.write(text, interval=0.05)  # 50ms between characters
        logger.info("Typed: '%s'", text[:50])
        return True
    except Exception as e:
        logger.error("Failed to type text: %s", e)
        return False
```

### Data Flow to Typing
```
User command "Type X in field Y"
    ↓
Planner creates step with action_type="type", value="X"
    ↓
Executor.execute_step(step)
    ↓
Routes to type_text(step["value"])
    ↓
⭐ pyautogui.write("X", interval=0.05)
```

### Input Sources
- **Primary**: `step["value"]` - Preferred parameter
- **Fallback**: `step["target"]` - If value is empty
- **Examples**:
  - `{"action_type": "type", "value": "hello world"}`
  - `{"action_type": "type_text", "target": "command to execute"}`

---

## 3. INTENT PARSER (Brain Layer)

### Current Intent Parser (Already Exists!)
**File**: `core/brain/intent_parser.py`  
**Class**: `IntentParser`

```python
@dataclass
class ParsedIntent:
    intent: str              # "send_email", "create_issue", etc.
    service: str             # "gmail", "github", "calendar", "os"
    confidence: float        # 0.0-1.0
    parameters: dict         # Extracted args
    response: str            # Human response
    raw_text: str            # LLM response
    
    def is_confident(self, threshold: float = 0.7) -> bool:
        return self.confidence >= threshold
```

### Intent Classifications (Existing)
```
"send_email"      → gmail service
"read_email"      → gmail service
"create_issue"    → github service
"create_event"    → calendar service
"open_app"        → os service
"take_screenshot" → os service
"unknown"         → fallback
```

### Two Parsing Modes
1. **Ollama-based** (if running):
   - Uses llama3 to parse
   - Returns JSON with intent, service, parameters
   - Falls back if Ollama unavailable

2. **Rule-based** (fallback):
   - Keyword matching (if command contains "email" → send_email)
   - Regex patterns for app names
   - Simple parameter extraction

### Used By
- `ActionRouter` - Routes to service-specific handlers
- Converts natural command → structured action

### LIMITATION: Text Content Not Classified
- IntentParser classifies **COMMAND intent** (what service/action)
- Does NOT classify **TEXT CONTENT intent** (what type of text)
- Gap: No distinction between:
  - Typing a password
  - Typing a message
  - Typing a code snippet
  - Typing a search query

---

## 4. ACTION ROUTER (Brain Layer)

### Current Action Router (Already Exists!)
**File**: `core/brain/action_router.py`  
**Class**: `ActionRouter`

```python
@dataclass
class RouteResult:
    success: bool
    output: str
    error: Optional[str]
    intent: str
    service: str

class ActionRouter:
    def route(self, user_id: str, intent: ParsedIntent) -> RouteResult:
        """Route parsed intent to appropriate handler."""
```

### Dispatch Handlers
```
Route: send_email
    → GmailAction.send_email(to, subject, body)
    
Route: read_email
    → GmailAction.read_inbox()
    
Route: create_issue
    → GitHubAction.create_issue(repo, title, body)
    
Route: create_event
    → CalendarAction.create_event(title, start, end, description)
    
Route: open_app
    → SecurityGateway.run_command(command)
    
Route: take_screenshot
    → SecurityGateway.take_screenshot(filename)
    
Route: unknown
    → Error response
```

### Used By
- Direct action execution for simple commands
- Bypasses planning if intent is clear
- Fast path for non-computer-control tasks

---

## 5. ELEMENT FINDER (Utilities)

### Purpose
Locates UI elements to click on without explicit coordinates

### Current Implementation
**File**: `utils/element_finder.py`  
**Class**: `ElementFinder`

```python
class ElementFinder:
    def find_by_name(
        name: str, 
        control_type: Optional[str] = None
    ) -> Optional[Tuple[int, int]]:
        """Find element by name/text. Returns (x, y) or None."""
    
    def find_button(text: str) -> Optional[Tuple[int, int]]:
        """Find button by text."""
    
    def find_text_field(label: str) -> Optional[Tuple[int, int]]:
        """Find text input by label."""
    
    def find_all_elements(
        window_title: Optional[str] = None
    ) -> List[Dict]:
        """List all accessible UI elements."""
```

### Implementation Details
- **On Windows**: Uses pywinauto + UIA backend (UI Automation)
- **On Other OS**: Would fall back to vision-based search
- **Returns**: Element center coordinates (x, y)

### When Used
- When plan step has `target="button name"` but no coordinates
- By executor's `find_and_click()` method
- Enables natural language element selection

---

## 6. VISION AGENT (Element Detection)

**File**: `agents/vision_agent.py`

### Purpose
- Analyzes screen screenshots
- Finds UI elements using computer vision (llava)
- Provides screen description for planning

### Key Methods
- `analyze_screen()` → Returns OCR + element locations
- `find_element(description)` → Uses vision to locate element
- Fallback when ElementFinder can't find element

### Used By
- Planner for screen context
- Executor for `find_and_click()` operations

---

## 7. VALIDATION AND HEALING

### Validation
**File**: `agents/validator_agent.py`

After each step execution:
1. Compare before/after screenshots
2. Check if expected outcome occurred
3. Return confidence score (0.0-1.0)

```python
ValidatorAgent.validate_step(
    step: dict,
    before_screenshot: str,
    after_screenshot: str
) → {"success": bool, "confidence": float, "reason": str}
```

### Self-Healing
**File**: `utils/self_healer.py`

If validation fails:
1. Analyze failure reason
2. Modify step or environment
3. Suggest retry modification
4. Up to 3 attempts per step

---

## 8. AGENTS INVOLVED IN COMMAND EXECUTION

| Agent | File | Role |
|-------|------|------|
| **RouterService** | core/router_service.py | Entry point, fast dispatch |
| **Router** | core/router.py | 2-tier task classification |
| **IntentParser** | core/brain/intent_parser.py | Command intent → service mapping |
| **ActionRouter** | core/brain/action_router.py | Service → handler dispatch |
| **Orchestrator** | agents/orchestrator.py | Master coordinator, pipeline |
| **VisionAgent** | agents/vision_agent.py | Screen analysis + element finding |
| **PlannerAgent** | agents/planner_agent.py | Step-by-step planning |
| **ExecutorAgent** | agents/executor_agent.py | Action execution (typing, clicks, etc.) |
| **ValidatorAgent** | agents/validator_agent.py | Result verification |
| **SelfHealer** | utils/self_healer.py | Failure recovery |
| **SafetyGuard** | utils/safety_guard.py | Risk assessment |
| **MemorySystem** | utils/memory_system.py | Episode storage + recall |

---

## 9. WHERE TO INSERT INTENT CLASSIFICATION LAYER

### Problem with Current Architecture
- ✅ Task-level intent is classified (send_email, open_app)
- ❌ Text CONTENT intent is NOT classified
- ❌ No way to distinguish:
  - Typing a password vs typing a message
  - Typing code vs typing natural language
  - Sensitive data vs public data

### Recommended Integration Points

#### Option 1: Task-Level Classification (RECOMMENDED)
**When**: After routing decision, before planning  
**Where**: `Orchestrator.run_task()` line ~120  
**What**: Classify overall task intent before plan creation

```python
# BEFORE (current):
plan = self.planner.create_plan(task_text, screen_description, memory_context)

# AFTER (proposed):
task_intent = self.task_intent_classifier.classify(task_text)
plan = self.planner.create_plan(
    task_text, 
    screen_description, 
    memory_context,
    task_intent=task_intent  # NEW
)
```

**Benefits**:
- Planner creates TARGETED steps based on intent
- Can adjust strategy per intent
- Reusable component across pipeline
- One Ollama call per task (acceptable cost)

#### Option 2: Text-Level Classification (HIGHLY RECOMMENDED)
**When**: Before typing text into field  
**Where**: `ExecutorAgent.type_text()` line ~365  
**What**: Analyze TEXT CONTENT before `pyautogui.write()`

```python
# BEFORE (current):
def type_text(self, text: str) -> bool:
    pyautogui.write(text, interval=0.05)

# AFTER (proposed):
def type_text(self, text: str) -> bool:
    # NEW: Analyze text first
    analysis = self.text_analyzer.analyze(text)
    
    if analysis.should_block:
        logger.error("Blocked: %s", analysis.reason)
        return False
    
    if analysis.should_warn:
        logger.warning("Warning: %s", analysis.warning)
    
    pyautogui.write(text, interval=0.05)
```

**Benefits**:
- Security: Detect PII/passwords
- Logging: Mask sensitive data in logs
- Validation: Ensure correct input type
- Prevention: Block dangerous inputs
- No Ollama calls needed (regex-based)

#### Option 3: Combined Approach (BEST)
Implement BOTH:
1. **Task-level** - Improve planning with intent context
2. **Text-level** - Secure execution with content analysis

```
User Command
    ↓
[NEW] Task Intent Classifier  ← Option 1
    ↓
Orchestrator → Planner (better plans)
    ↓
Executor.execute_step()
    ├─ [NEW] Text Intent Analyzer  ← Option 2
    └─ type_text() → pyautogui.write()
```

### Implementation Effort Estimate

| Component | Lines | LLM? | Time | Priority |
|-----------|-------|------|------|----------|
| Task Intent Classifier | 100-150 | Yes | 2-3h | HIGH |
| Text Intent Analyzer | 150-200 | No* | 1-2h | VERY HIGH |
| Integration (Orch) | 10-15 | - | 30min | - |
| Integration (Exec) | 10-15 | - | 30min | - |

*Uses regex patterns + rule-based logic, not LLM

### Detailed Implementation Plan

#### Text Intent Analyzer First (Low-risk, high-value)
1. Create pattern-based PII detector
2. Classify input types (password, email, code, normal)
3. Add confidence scoring
4. Insert into type_text() before pyautogui.write()
5. Test with sensitive data

#### Task Intent Classifier Second
1. Reuse existing IntentParser as base
2. Add task-level analysis
3. Return intent + confidence
4. Integrate with Orchestrator
5. Update Planner to use intent context

---

## 10. COMPLETE INFORMATION SUMMARY TABLE

| Aspect | Details |
|--------|---------|
| **Entry Point** | `RouterService.handle_task(task_text)` |
| **Fast Router** | `Router.route()` - 2-tier classification |
| **Complex Tasks** | `Orchestrator.run_task()` - Full pipeline |
| **Planning** | `PlannerAgent.create_plan()` - Ollama llama3 |
| **Step Execution** | `ExecutorAgent.execute_step(step)` |
| **Text Typing** | `ExecutorAgent.type_text()` - pyautogui.write() |
| **Typing Input** | `step["value"]` (from plan) |
| **Intent Parsing** | `IntentParser` - Command intent classification |
| **Intent Routing** | `ActionRouter` - Service-specific dispatch |
| **Element Finding** | `ElementFinder` - UI element location |
| **Vision Support** | `VisionAgent` - Screen analysis + OCR |
| **Validation** | `ValidatorAgent` - Result verification |
| **Error Recovery** | `SelfHealer` - Failure recovery (up to 3 retries) |
| **Safety** | `SafetyGuard` - Risk assessment + user confirmation |
| **Memory** | `MemorySystem` - Episode storage for learning |

---

## 11. FILES REFERENCED

### Core Agents
- `agents/orchestrator.py` - Master coordinator
- `agents/executor_agent.py` - Action execution
- `agents/planner_agent.py` - Step planning
- `agents/vision_agent.py` - Screen analysis
- `agents/validator_agent.py` - Result validation

### Brain Layer
- `core/brain/intent_parser.py` - Command intent classification
- `core/brain/action_router.py` - Service dispatch
- `core/router.py` - Fast 2-tier routing

### Utilities
- `core/router_service.py` - Entry point service
- `utils/element_finder.py` - UI element location
- `utils/self_healer.py` - Failure recovery
- `utils/safety_guard.py` - Risk assessment
- `utils/memory_system.py` - Episode storage

### Config
- `config/settings.yaml` - Ollama + model config
- `config/safety_rules.yaml` - Safety policies

### Entry
- `main.py` - CLI entry point

---

## 12. KEY INSIGHTS FOR INTENT CLASSIFIER

### Current Architecture Strengths
✅ Command intent IS classified (email, github, calendar)  
✅ Clear routing to appropriate handlers  
✅ Memory system learns from episodes  
✅ Safety layer exists for risk assessment  
✅ Planner uses Ollama for sophisticated reasoning  

### Current Architecture Gaps
❌ No classification of TEXT CONTENT  
❌ No PII/sensitive data detection  
❌ No input type validation (password vs text vs code)  
❌ No purpose analysis for typing  
❌ Generic typing without context  

### Why It Matters for Typing
- **Security**: Detect when typing passwords or credentials
- **Logging**: Mask sensitive data in logs
- **Reliability**: Detect wrong input type early
- **Context**: Executor can adapt behavior based on content type
- **User Trust**: Show warnings for sensitive operations

### Design Principles for New Classifier
1. **Separate concerns**: Text analysis ≠ task routing
2. **Non-intrusive**: Insert without breaking existing flow
3. **Layered approach**: Task-level AND text-level
4. **Performance**: Text analyzer should use regex, not LLM
5. **Confidence-based**: Always return confidence score
6. **Actionable results**: Enable warn, block, log masking
7. **Reusable**: Can be used elsewhere in codebase
8. **Testable**: Clear input/output contracts

---

## Quick Reference: Data Flowing to type_text()

```
Plan Step Dict:
{
    "step_number": 2,
    "action_type": "type",           ← Router uses this
    "description": "Enter password",
    "target": null,
    "value": "secretpassword123",    ← GOES HERE
    "expected_outcome": "Password accepted",
    "timeout": 10
}
    ↓
ExecutorAgent.execute_step(step)
    ↓
Routes by action_type → "type"
    ↓
ExecutorAgent.type_text(step["value"])
    ↓
    ⭐ INPUT: "secretpassword123"
    ⭐ [NEW] Analyze intent → "password", confidence: 0.95
    ⭐ [NEW] Detect PII → ["password_pattern"]  
    ⭐ [NEW] Safety check → should_warn=True
    ⭐ EXECUTE: pyautogui.write("secretpassword123", interval=0.05)
```

---

## Notes

- All AI reasoning uses LOCAL Ollama (zero external APIs)
- Typing uses pyautogui with 50ms intervals between characters
- Plans are JSON with strict action_type constraints
- Validation is vision-based (before/after screenshots)
- Memory stores episodes for future similar tasks
- Safety guard can block/confirm sensitive actions
- Multi-retry with healing for fault tolerance

