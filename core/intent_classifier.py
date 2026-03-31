"""Advanced Intent Classification System

Classifies user commands into structured intent types before execution.
This prevents incorrect behavior like typing entire instructions instead 
of following the proper execution pipeline.

Intent Types:
- OPEN_APP: Open an application
- WEB_SEARCH: Search on the web
- OPEN_URL: Navigate to a URL
- TYPE_TEXT: Type freeform text
- CLICK: Click on an element
- SCROLL: Scroll on page
- FILE_OPEN: Open a file
- FILE_SAVE: Save a file
- NAVIGATION: Navigate in app
- FORM_FILL: Fill out a form
- SYSTEM: System commands
- CUSTOM_WORKFLOW: Use saved workflow
- UNKNOWN: Fallback/ambiguous
"""

import re
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import json


class IntentType(Enum):
    """Intent type enumeration"""
    OPEN_APP = "open_app"
    WEB_SEARCH = "web_search"
    OPEN_URL = "open_url"
    TYPE_TEXT = "type_text"
    CLICK = "click"
    SCROLL = "scroll"
    FILE_OPEN = "file_open"
    FILE_SAVE = "file_save"
    NAVIGATION = "navigation"
    FORM_FILL = "form_fill"
    SYSTEM = "system"
    CUSTOM_WORKFLOW = "custom_workflow"
    UNKNOWN = "unknown"


@dataclass
class IntentResult:
    """Structured result of intent classification"""
    intent: IntentType
    confidence: float  # 0.0 to 1.0
    parameters: Dict[str, Any]
    reasoning: str
    suggested_workflow: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        result = asdict(self)
        result['intent'] = self.intent.value
        return result


class IntentClassifier:
    """Classifies user commands into structured intents"""
    
    # Pattern definitions for intent recognition
    APP_PATTERNS = {
        'chrome|google chrome': 'Chrome',
        'edge|microsoft edge': 'Edge',
        'firefox': 'Firefox',
        'outlook|mail': 'Outlook',
        'excel|spreadsheet': 'Excel',
        'word|document': 'Word',
        'whatsapp|whats app': 'WhatsApp',
        'telegram': 'Telegram',
        'slack': 'Slack',
        'discord': 'Discord',
        'zoom': 'Zoom',
        'teams|microsoft teams': 'Teams',
        'vscode|vs code|visual studio': 'VS Code',
        'notepad|text editor': 'Notepad',
        'photoshop|image editor': 'Photoshop',
        'vlc|video player': 'VLC',
        'spotify|music': 'Spotify',
        'youtube|video': 'YouTube',
    }
    
    WEB_SEARCH_KEYWORDS = {
        'search', 'find', 'look for', 'google', 'query', 'search for',
        'research', 'what is', 'how', 'when', 'where', 'who'
    }
    
    CLICK_KEYWORDS = {
        'click', 'press', 'tap', 'select', 'choose', 'activate',
        'hit', 'push', 'touch', 'focus'
    }
    
    SCROLL_KEYWORDS = {
        'scroll', 'page down', 'page up', 'down', 'up', 'bottom', 'top'
    }
    
    FILE_KEYWORDS = {
        'open file', 'load file', 'read file', 'access file',
        'open report', 'open document', 'view file'
    }
    
    SYSTEM_KEYWORDS = {
        'shutdown', 'restart', 'sleep', 'lock', 'logoff', 'exit',
        'close', 'minimize', 'maximize', 'window'
    }
    
    TYPE_KEYWORDS = {
        'type', 'write', 'enter', 'input', 'compose', 'draft',
        'message', 'say', 'tell', 'respond'
    }
    
    URL_PATTERNS = r'^(https?://|www\.|\.com|\.org|\.net|\.io)'
    
    def classify(self, command: str) -> IntentResult:
        """
        Classify a user command into an intent type
        
        Args:
            command: User's natural language command
            
        Returns:
            IntentResult with classified intent and parameters
        """
        command_lower = command.lower().strip()
        
        # Try progressive classification strategies
        result = self._try_url_intent(command_lower)
        if result.intent != IntentType.UNKNOWN:
            return result
        
        result = self._try_app_intent(command_lower)
        if result.intent != IntentType.UNKNOWN:
            return result
        
        result = self._try_web_search_intent(command_lower)
        if result.intent != IntentType.UNKNOWN:
            return result
        
        result = self._try_file_intent(command_lower)
        if result.intent != IntentType.UNKNOWN:
            return result
        
        result = self._try_click_intent(command_lower)
        if result.intent != IntentType.UNKNOWN:
            return result
        
        result = self._try_scroll_intent(command_lower)
        if result.intent != IntentType.UNKNOWN:
            return result
        
        result = self._try_system_intent(command_lower)
        if result.intent != IntentType.UNKNOWN:
            return result
        
        # Check for navigation/form patterns
        result = self._try_navigation_intent(command_lower)
        if result.intent != IntentType.UNKNOWN:
            return result
        
        # Default to unknown
        return IntentResult(
            intent=IntentType.UNKNOWN,
            confidence=0.0,
            parameters={},
            reasoning="Could not classify command into known intent types",
            suggested_workflow="manual_planning"
        )
    
    def _try_url_intent(self, command: str) -> IntentResult:
        """Try to identify URL intent"""
        # Check for direct URL
        if re.search(self.URL_PATTERNS, command):
            url = self._extract_url(command)
            if url:
                return IntentResult(
                    intent=IntentType.OPEN_URL,
                    confidence=0.95,
                    parameters={'url': url},
                    reasoning=f"Detected URL pattern: {url}",
                    suggested_workflow="open_url_workflow"
                )
        
        # Check for "go to" pattern
        if any(phrase in command for phrase in ['go to', 'visit', 'navigate to', 'open url']):
            url = self._extract_url(command)
            if url:
                return IntentResult(
                    intent=IntentType.OPEN_URL,
                    confidence=0.9,
                    parameters={'url': url},
                    reasoning="Detected navigation intent with URL",
                    suggested_workflow="open_url_workflow"
                )
        
        return IntentResult(
            intent=IntentType.UNKNOWN,
            confidence=0.0,
            parameters={},
            reasoning="No URL pattern detected"
        )
    
    def _try_app_intent(self, command: str) -> IntentResult:
        """Try to identify app opening intent"""
        # Check if command starts with "open"
        if command.startswith('open '):
            app_name = command[5:].strip()
            
            # Try to match against known apps
            matched_app = self._match_app_name(app_name)
            if matched_app:
                # Check if also contains search (compound intent)
                if any(keyword in command for keyword in ['search', 'find', 'look for']):
                    # Extract search query
                    query = self._extract_after_keyword(command, ['search', 'find', 'look for'])
                    return IntentResult(
                        intent=IntentType.WEB_SEARCH,
                        confidence=0.9,
                        parameters={
                            'app': matched_app,
                            'query': query,
                            'action': 'open_and_search'
                        },
                        reasoning=f"Detected compound intent: open {matched_app} and search for {query}",
                        suggested_workflow="web_search_workflow"
                    )
                
                # Pure app opening
                return IntentResult(
                    intent=IntentType.OPEN_APP,
                    confidence=0.95,
                    parameters={'app': matched_app},
                    reasoning=f"Detected open app intent: {matched_app}",
                    suggested_workflow="open_app_workflow"
                )
        
        return IntentResult(
            intent=IntentType.UNKNOWN,
            confidence=0.0,
            parameters={},
            reasoning="No app open intent detected"
        )
    
    def _try_web_search_intent(self, command: str) -> IntentResult:
        """Try to identify web search intent"""
        for keyword in self.WEB_SEARCH_KEYWORDS:
            if keyword in command:
                # Get search query (everything after keyword)
                query = self._extract_query_after_keyword(command, keyword)
                if query:
                    return IntentResult(
                        intent=IntentType.WEB_SEARCH,
                        confidence=0.85,
                        parameters={'query': query},
                        reasoning=f"Detected web search from keyword '{keyword}': {query}",
                        suggested_workflow="web_search_workflow"
                    )
        
        return IntentResult(
            intent=IntentType.UNKNOWN,
            confidence=0.0,
            parameters={},
            reasoning="No web search intent detected"
        )
    
    def _try_file_intent(self, command: str) -> IntentResult:
        """Try to identify file operation intent"""
        for keyword in self.FILE_KEYWORDS:
            if keyword in command:
                filename = self._extract_filename(command)
                return IntentResult(
                    intent=IntentType.FILE_OPEN,
                    confidence=0.85,
                    parameters={'filename': filename},
                    reasoning=f"Detected file open from keyword '{keyword}'",
                    suggested_workflow="file_open_workflow"
                )
        
        if 'save' in command or 'save as' in command:
            filename = self._extract_filename(command)
            return IntentResult(
                intent=IntentType.FILE_SAVE,
                confidence=0.85,
                parameters={'filename': filename},
                reasoning="Detected file save intent",
                suggested_workflow="file_save_workflow"
            )
        
        return IntentResult(
            intent=IntentType.UNKNOWN,
            confidence=0.0,
            parameters={},
            reasoning="No file operation intent detected"
        )
    
    def _try_click_intent(self, command: str) -> IntentResult:
        """Try to identify click intent"""
        for keyword in self.CLICK_KEYWORDS:
            if keyword in command:
                element = self._extract_element_name(command, keyword)
                return IntentResult(
                    intent=IntentType.CLICK,
                    confidence=0.8,
                    parameters={'element': element},
                    reasoning=f"Detected click intent on element: {element}",
                    suggested_workflow="click_workflow"
                )
        
        return IntentResult(
            intent=IntentType.UNKNOWN,
            confidence=0.0,
            parameters={},
            reasoning="No click intent detected"
        )
    
    def _try_scroll_intent(self, command: str) -> IntentResult:
        """Try to identify scroll intent"""
        for keyword in self.SCROLL_KEYWORDS:
            if keyword in command:
                direction = 'down' if any(w in command for w in ['down', 'bottom']) else 'up'
                amount = self._extract_number(command) or 5
                
                return IntentResult(
                    intent=IntentType.SCROLL,
                    confidence=0.85,
                    parameters={'direction': direction, 'amount': amount},
                    reasoning=f"Detected scroll intent: {direction} {amount} units",
                    suggested_workflow="scroll_workflow"
                )
        
        return IntentResult(
            intent=IntentType.UNKNOWN,
            confidence=0.0,
            parameters={},
            reasoning="No scroll intent detected"
        )
    
    def _try_system_intent(self, command: str) -> IntentResult:
        """Try to identify system command intent"""
        for keyword in self.SYSTEM_KEYWORDS:
            if keyword in command:
                return IntentResult(
                    intent=IntentType.SYSTEM,
                    confidence=0.9,
                    parameters={'command': keyword},
                    reasoning=f"Detected system command: {keyword}",
                    suggested_workflow="system_command_workflow"
                )
        
        return IntentResult(
            intent=IntentType.UNKNOWN,
            confidence=0.0,
            parameters={},
            reasoning="No system command detected"
        )
    
    def _try_navigation_intent(self, command: str) -> IntentResult:
        """Try to identify navigation or form intent"""
        # This is a catch-all for complex multi-step operations
        keywords = ['fill', 'complete', 'submit', 'navigate', 'go to', 'move to']
        for keyword in keywords:
            if keyword in command:
                return IntentResult(
                    intent=IntentType.NAVIGATION,
                    confidence=0.6,
                    parameters={'action': keyword},
                    reasoning=f"Detected navigation/form operation: {keyword}",
                    suggested_workflow="manual_planning"
                )
        
        return IntentResult(
            intent=IntentType.UNKNOWN,
            confidence=0.0,
            parameters={},
            reasoning="No navigation intent detected"
        )
    
    # Helper methods
    
    def _match_app_name(self, app_text: str) -> Optional[str]:
        """Match user input to known app names"""
        app_text_lower = app_text.lower()
        
        for patterns, app_name in self.APP_PATTERNS.items():
            for pattern in patterns.split('|'):
                if pattern.strip() in app_text_lower:
                    return app_name
        
        return None
    
    def _extract_url(self, text: str) -> Optional[str]:
        """Extract URL from text"""
        urls = re.findall(r'(https?://[^\s]+|www\.[^\s]+|[a-zA-Z0-9-]+\.(?:com|org|net|io|co)[^\s]*)', text)
        if urls:
            return urls[0]
        return None
    
    def _extract_query_after_keyword(self, text: str, keyword: str) -> Optional[str]:
        """Extract search query after a keyword"""
        parts = text.split(keyword, 1)
        if len(parts) > 1:
            return parts[1].strip()
        return None
    
    def _extract_after_keyword(self, text: str, keywords: List[str]) -> str:
        """Extract text after any of the keywords"""
        for keyword in keywords:
            if keyword in text:
                parts = text.split(keyword, 1)
                return parts[1].strip() if len(parts) > 1 else ""
        return text
    
    def _extract_filename(self, text: str) -> str:
        """Extract filename from text"""
        # Look for quoted strings or file extensions
        quoted = re.findall(r'"([^"]+)"', text)
        if quoted:
            return quoted[0]
        
        # Look for file extensions
        files = re.findall(r'\b([a-zA-Z0-9_-]+\.[a-zA-Z0-9]+)\b', text)
        if files:
            return files[0]
        
        return "file"
    
    def _extract_element_name(self, text: str, keyword: str) -> str:
        """Extract element name from click intent"""
        parts = text.split(keyword, 1)
        if len(parts) > 1:
            element = parts[1].strip()
            # Remove common words
            element = re.sub(r'\s(button|link|field|input|tab|menu|icon)\b', '', element)
            return element[:50]  # Limit length
        return "element"
    
    def _extract_number(self, text: str) -> Optional[int]:
        """Extract first number from text"""
        numbers = re.findall(r'\d+', text)
        if numbers:
            return int(numbers[0])
        return None


# Workflow templates for common intents
WORKFLOW_TEMPLATES = {
    'open_app_workflow': [
        {'step': 1, 'action': 'press', 'value': 'win', 'description': 'Open start menu'},
        {'step': 2, 'action': 'wait', 'value': 500, 'description': 'Wait for menu to appear'},
        {'step': 3, 'action': 'type', 'value': '{app}', 'description': 'Type app name'},
        {'step': 4, 'action': 'wait', 'value': 500, 'description': 'Wait for search'},
        {'step': 5, 'action': 'press', 'value': 'enter', 'description': 'Launch app'},
        {'step': 6, 'action': 'wait', 'value': 2000, 'description': 'Wait for app to open'},
    ],
    
    'web_search_workflow': [
        {'step': 1, 'action': 'open_app', 'value': '{app}', 'description': 'Open browser'},
        {'step': 2, 'action': 'wait', 'value': 2000, 'description': 'Wait for browser to load'},
        {'step': 3, 'action': 'click', 'value': 'address_bar', 'description': 'Click address bar'},
        {'step': 4, 'action': 'type', 'value': '{query}', 'description': 'Type search query'},
        {'step': 5, 'action': 'press', 'value': 'enter', 'description': 'Search'},
        {'step': 6, 'action': 'wait', 'value': 2000, 'description': 'Wait for results'},
    ],
    
    'open_url_workflow': [
        {'step': 1, 'action': 'open_app', 'value': 'Chrome', 'description': 'Open browser'},
        {'step': 2, 'action': 'wait', 'value': 2000, 'description': 'Wait for browser'},
        {'step': 3, 'action': 'click', 'value': 'address_bar', 'description': 'Click address bar'},
        {'step': 4, 'action': 'type', 'value': '{url}', 'description': 'Type URL'},
        {'step': 5, 'action': 'press', 'value': 'enter', 'description': 'Navigate'},
        {'step': 6, 'action': 'wait', 'value': 3000, 'description': 'Wait for page load'},
    ],
    
    'click_workflow': [
        {'step': 1, 'action': 'detect_screen', 'value': None, 'description': 'Detect current screen'},
        {'step': 2, 'action': 'click', 'value': '{element}', 'description': 'Click element'},
        {'step': 3, 'action': 'wait', 'value': 500, 'description': 'Wait for click effect'},
    ],
    
    'scroll_workflow': [
        {'step': 1, 'action': 'scroll', 'value': '{direction}:{amount}', 'description': 'Scroll'},
        {'step': 2, 'action': 'wait', 'value': 500, 'description': 'Wait for scroll'},
    ],
}


def get_workflow_template(workflow_name: str) -> Optional[List[Dict[str, Any]]]:
    """Get a workflow template by name"""
    return WORKFLOW_TEMPLATES.get(workflow_name)
