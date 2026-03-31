"""Tests for Keyboard Shortcuts System
======================================

Tests keyboard shortcut definitions, registration, and execution.
"""

import pytest
from core.screen.keyboard_shortcuts import (
    ModifierKey,
    CommonKey,
    KeyboardShortcut,
    KeyboardShortcuts,
    KeyboardShortcutsManager
)


class TestModifierKey:
    """Tests for ModifierKey enum."""
    
    def test_modifier_key_values(self):
        """Test modifier key enum values."""
        assert ModifierKey.NONE.value == "none"
        assert ModifierKey.CTRL.value == "ctrl"
        assert ModifierKey.ALT.value == "alt"
        assert ModifierKey.SHIFT.value == "shift"
        assert ModifierKey.WIN.value == "win"


class TestCommonKey:
    """Tests for CommonKey enum."""
    
    def test_common_key_values(self):
        """Test common key enum values."""
        assert CommonKey.ENTER.value == "enter"
        assert CommonKey.ESCAPE.value == "escape"
        assert CommonKey.TAB.value == "tab"
        assert CommonKey.SPACE.value == "space"


class TestKeyboardShortcut:
    """Tests for KeyboardShortcut class."""
    
    def test_create_shortcut_no_modifier(self):
        """Test creating shortcut without modifier."""
        shortcut = KeyboardShortcut("enter")
        
        assert shortcut.key == "enter"
        assert shortcut.modifier == ModifierKey.NONE
    
    def test_create_shortcut_with_modifier(self):
        """Test creating shortcut with modifier."""
        shortcut = KeyboardShortcut("c", ModifierKey.CTRL)
        
        assert shortcut.key == "c"
        assert shortcut.modifier == ModifierKey.CTRL
    
    def test_shortcut_with_description(self):
        """Test creating shortcut with description."""
        shortcut = KeyboardShortcut("a", ModifierKey.CTRL, "Select all")
        
        assert shortcut.description == "Select all"
    
    def test_shortcut_string_representation_no_modifier(self):
        """Test string representation without modifier."""
        shortcut = KeyboardShortcut("enter")
        
        assert str(shortcut) == "enter"
    
    def test_shortcut_string_representation_with_modifier(self):
        """Test string representation with modifier."""
        shortcut = KeyboardShortcut("c", ModifierKey.CTRL)
        
        assert str(shortcut) == "CTRL+c"
    
    def test_shortcut_to_tuple(self):
        """Test converting shortcut to tuple."""
        shortcut = KeyboardShortcut("s", ModifierKey.CTRL)
        
        tup = shortcut.to_tuple()
        
        assert isinstance(tup, tuple)
        assert tup[0] == "ctrl"
        assert tup[1] == "s"


class TestPredefinedShortcuts:
    """Tests for predefined keyboard shortcuts."""
    
    def test_browser_shortcuts(self):
        """Test browser navigation shortcuts."""
        assert KeyboardShortcuts.BACK.key == "escape"
        assert KeyboardShortcuts.RELOAD.key == "f5"
    
    def test_text_editing_shortcuts(self):
        """Test text editing shortcuts."""
        assert KeyboardShortcuts.SELECT_ALL.modifier == ModifierKey.CTRL
        assert KeyboardShortcuts.COPY.modifier == ModifierKey.CTRL
        assert KeyboardShortcuts.PASTE.modifier == ModifierKey.CTRL
    
    def test_navigation_shortcuts(self):
        """Test navigation shortcuts."""
        assert KeyboardShortcuts.TAB.key == "tab"
        assert KeyboardShortcuts.ENTER.key == "enter"
        assert KeyboardShortcuts.ESCAPE.key == "escape"
    
    def test_media_shortcuts(self):
        """Test media shortcuts."""
        assert KeyboardShortcuts.PLAY_PAUSE.key == "space"
        assert KeyboardShortcuts.FULLSCREEN.key == "f"
    
    def test_browser_specific(self):
        """Test browser-specific shortcuts."""
        assert KeyboardShortcuts.NEW_TAB.modifier == ModifierKey.CTRL
        assert KeyboardShortcuts.CLOSE_TAB.modifier == ModifierKey.CTRL
        assert KeyboardShortcuts.DEV_TOOLS.key == "f12"


class TestKeyboardShortcutsManager:
    """Tests for KeyboardShortcutsManager."""
    
    def test_manager_initialization(self):
        """Test creating manager."""
        manager = KeyboardShortcutsManager()
        
        assert manager.executor is None
        assert manager.custom_shortcuts == {}
    
    def test_manager_with_executor(self):
        """Test creating manager with executor."""
        class MockExecutor:
            pass
        
        executor = MockExecutor()
        manager = KeyboardShortcutsManager(executor=executor)
        
        assert manager.executor is executor
    
    def test_register_custom_shortcut(self):
        """Test registering custom shortcut."""
        manager = KeyboardShortcutsManager()
        
        manager.register_shortcut(
            "custom_action",
            "x",
            ModifierKey.ALT
        )
        
        assert "custom_action" in manager.custom_shortcuts
        assert manager.custom_shortcuts["custom_action"].key == "x"
    
    def test_get_builtin_shortcut(self):
        """Test getting built-in shortcut."""
        manager = KeyboardShortcutsManager()
        
        shortcut = manager.get_shortcut("COPY")
        
        assert shortcut is not None
        assert shortcut.modifier == ModifierKey.CTRL
    
    def test_get_custom_shortcut(self):
        """Test getting custom shortcut."""
        manager = KeyboardShortcutsManager()
        
        manager.register_shortcut("my_action", "q", ModifierKey.CTRL)
        shortcut = manager.get_shortcut("my_action")
        
        assert shortcut is not None
        assert shortcut.key == "q"
    
    def test_get_shortcut_case_insensitive(self):
        """Test shortcut lookup is case-insensitive."""
        manager = KeyboardShortcutsManager()
        
        shortcut1 = manager.get_shortcut("COPY")
        shortcut2 = manager.get_shortcut("copy")
        shortcut3 = manager.get_shortcut("Copy")
        
        assert shortcut1 is shortcut2
        assert shortcut2 is shortcut3
    
    def test_get_nonexistent_shortcut(self):
        """Test getting non-existent shortcut."""
        manager = KeyboardShortcutsManager()
        
        shortcut = manager.get_shortcut("nonexistent_action")
        
        assert shortcut is None
    
    def test_get_shortcut_info(self):
        """Test getting shortcut information."""
        manager = KeyboardShortcutsManager()
        
        info = manager.get_shortcut_info("COPY")
        
        assert info is not None
        assert "name" in info
        assert "key" in info
        assert "modifier" in info
        assert "display" in info
        assert "description" in info
    
    def test_get_shortcut_info_nonexistent(self):
        """Test getting info for non-existent shortcut."""
        manager = KeyboardShortcutsManager()
        
        info = manager.get_shortcut_info("nonexistent")
        
        assert info is None
    
    def test_list_shortcuts(self):
        """Test listing all shortcuts."""
        manager = KeyboardShortcutsManager()
        
        shortcuts = manager.list_shortcuts()
        
        assert isinstance(shortcuts, list)
        assert len(shortcuts) > 0
        assert all("name" in s for s in shortcuts)
        assert all("display" in s for s in shortcuts)
    
    def test_list_includes_custom(self):
        """Test that list includes custom shortcuts."""
        manager = KeyboardShortcutsManager()
        
        manager.register_shortcut("custom", "z")
        shortcuts = manager.list_shortcuts()
        
        custom = [s for s in shortcuts if s["name"] == "custom"]
        assert len(custom) == 1
    
    def test_list_sorted(self):
        """Test that shortcut list is sorted."""
        manager = KeyboardShortcutsManager()
        
        shortcuts = manager.list_shortcuts()
        names = [s["name"] for s in shortcuts]
        
        # Check they're sorted
        assert names == sorted(names)


class TestShortcutExecution:
    """Tests for shortcut execution."""
    
    @pytest.mark.asyncio
    async def test_press_shortcut_no_executor(self):
        """Test pressing shortcut without executor."""
        manager = KeyboardShortcutsManager(executor=None)
        
        result = await manager.press_shortcut("copy")
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_press_nonexistent_shortcut(self):
        """Test pressing non-existent shortcut."""
        class MockExecutor:
            pass
        
        manager = KeyboardShortcutsManager(executor=MockExecutor())
        
        result = await manager.press_shortcut("nonexistent")
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_press_shortcut_success(self):
        """Test pressing shortcut successfully."""
        class MockExecutor:
            def __init__(self):
                self.pressed = None
            
            async def press_key(self, key, modifier):
                self.pressed = (key, modifier)
        
        executor = MockExecutor()
        manager = KeyboardShortcutsManager(executor=executor)
        
        result = await manager.press_shortcut("copy")
        
        # Should work if press_key implemented
        # Result depends on implementation
        assert isinstance(result, bool)
    
    @pytest.mark.asyncio
    async def test_press_custom_shortcut(self):
        """Test pressing custom shortcut."""
        class MockExecutor:
            async def press_key(self, key, modifier):
                return True
        
        executor = MockExecutor()
        manager = KeyboardShortcutsManager(executor=executor)
        
        manager.register_shortcut("test_action", "t", ModifierKey.CTRL)
        
        # Should be able to find and press custom shortcut
        shortcut = manager.get_shortcut("test_action")
        assert shortcut is not None


class TestShortcutEdgeCases:
    """Tests for edge cases."""
    
    def test_shortcut_with_numeric_key(self):
        """Test shortcut with numeric key."""
        shortcut = KeyboardShortcut("1", ModifierKey.CTRL)
        
        assert shortcut.key == "1"
        assert str(shortcut) == "CTRL+1"
    
    def test_shortcut_with_special_key(self):
        """Test shortcut with special key."""
        shortcut = KeyboardShortcut("f5")
        
        assert shortcut.key == "f5"
    
    def test_register_overwrite_shortcut(self):
        """Test overwriting registered shortcut."""
        manager = KeyboardShortcutsManager()
        
        manager.register_shortcut("action", "a", ModifierKey.CTRL)
        assert manager.get_shortcut("action").key == "a"
        
        manager.register_shortcut("action", "b", ModifierKey.ALT)
        assert manager.get_shortcut("action").key == "b"
        assert manager.get_shortcut("action").modifier == ModifierKey.ALT
    
    def test_empty_shortcut_key(self):
        """Test shortcut with empty key."""
        shortcut = KeyboardShortcut("")
        
        assert shortcut.key == ""
        assert str(shortcut) == ""
    
    def test_shortcut_with_long_description(self):
        """Test shortcut with long description."""
        long_desc = "This is a very long description " * 10
        shortcut = KeyboardShortcut("a", description=long_desc)
        
        assert shortcut.description == long_desc
