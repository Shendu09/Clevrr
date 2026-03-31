"""Tests for Screen State Coordinator
====================================

Tests integration coordinator functionality.
"""

import pytest
from core.screen.coordinator import ScreenStateCoordinator, ScreenStateConfig


class TestScreenStateConfig:
    """Tests for ScreenStateConfig."""
    
    def test_config_defaults(self):
        """Test default configuration."""
        config = ScreenStateConfig()
        
        assert config.enable_vision_detection is True
        assert config.enable_ocr is True
        assert config.max_cached_screenshots == 20
        assert config.retry_max_attempts == 3
    
    def test_config_custom(self):
        """Test custom configuration."""
        config = ScreenStateConfig(
            enable_vision_detection=False,
            max_cached_screenshots=50,
            retry_max_attempts=5
        )
        
        assert config.enable_vision_detection is False
        assert config.max_cached_screenshots == 50
        assert config.retry_max_attempts == 5


class TestScreenStateCoordinator:
    """Tests for ScreenStateCoordinator."""
    
    def test_coordinator_initialization(self):
        """Test coordinator initialization."""
        coordinator = ScreenStateCoordinator()
        
        assert coordinator.detector is not None
        assert coordinator.router is not None
        assert coordinator.text_detector is not None
    
    def test_coordinator_with_executor(self):
        """Test coordinator with executor."""
        class MockExecutor:
            pass
        
        executor = MockExecutor()
        coordinator = ScreenStateCoordinator(executor=executor)
        
        assert coordinator.executor is executor
    
    def test_coordinator_with_vision_agent(self):
        """Test coordinator with vision agent."""
        class MockVision:
            pass
        
        vision = MockVision()
        coordinator = ScreenStateCoordinator(vision_agent=vision)
        
        assert coordinator.vision_agent is vision
    
    def test_coordinator_with_custom_config(self):
        """Test coordinator with custom config."""
        config = ScreenStateConfig(max_cached_screenshots=50)
        coordinator = ScreenStateCoordinator(config=config)
        
        assert coordinator.config.max_cached_screenshots == 50
    
    def test_coordinator_disabled_subsystems(self):
        """Test coordinator with disabled subsystems."""
        config = ScreenStateConfig(
            enable_vision_detection=False,
            enable_ocr=False
        )
        coordinator = ScreenStateCoordinator(config=config)
        
        assert coordinator.detector is not None  # Still created


class TestCoordinatorStatus:
    """Tests for coordinator status reporting."""
    
    def test_get_system_status(self):
        """Test getting system status."""
        coordinator = ScreenStateCoordinator()
        
        status = coordinator.get_system_status()
        
        assert "detector_ready" in status
        assert "router_ready" in status
        assert "action_logger_history" in status
        assert "cached_screenshots" in status
        assert status["detector_ready"] is True
        assert status["router_ready"] is True
    
    def test_get_action_summary(self):
        """Test getting action summary."""
        coordinator = ScreenStateCoordinator()
        
        summary = coordinator.get_action_summary()
        
        assert "total_actions" in summary
        assert "failed_actions" in summary
        assert "success_rate" in summary
    
    def test_get_all_shortcuts(self):
        """Test getting all shortcuts."""
        coordinator = ScreenStateCoordinator()
        
        shortcuts = coordinator.get_all_shortcuts()
        
        assert isinstance(shortcuts, list)
        assert len(shortcuts) > 0


class TestCoordinatorOperations:
    """Tests for coordinator operations."""
    
    @pytest.mark.asyncio
    async def test_process_task(self):
        """Test processing a task."""
        class MockDetector:
            def detect_screen(self, screenshot):
                from core.screen.screen_types import ScreenType
                from core.screen.screen_detector import ScreenDetectionResult
                
                return ScreenDetectionResult(
                    screen_type=ScreenType.DESKTOP,
                    confidence=0.95,
                    detected_elements=[]
                )
        
        coordinator = ScreenStateCoordinator()
        coordinator.detector = MockDetector()
        
        result = await coordinator.process_task(
            "Open notepad",
            b"test_screenshot"
        )
        
        assert isinstance(result, dict)
        assert "success" in result
        assert "screen_type" in result
    
    def test_register_handler(self):
        """Test registering a handler."""
        coordinator = ScreenStateCoordinator()
        from core.screen.screen_types import ScreenType
        from core.screen.screen_handler import ScreenHandler
        
        class TestHandler(ScreenHandler):
            async def handle(self, task, screenshot):
                return {"success": True}
        
        handler = TestHandler()
        coordinator.register_handler(ScreenType.DESKTOP, handler)
        
        # Handler should be registered
        assert coordinator.router.handlers is not None
    
    def test_clear_cache(self):
        """Test clearing caches."""
        coordinator = ScreenStateCoordinator()
        
        # Add something to cache
        coordinator.action_logger.log_click(target="btn", x=0, y=0)
        coordinator.screenshot_cache.add(b"test")
        
        assert coordinator.screenshot_cache.size() == 1
        
        # Clear
        coordinator.clear_cache()
        
        assert coordinator.screenshot_cache.size() == 0
        assert len(coordinator.action_logger.history) == 0


class TestCoordinatorConfiguration:
    """Tests for configuration handling."""
    
    def test_vision_detection_disabled(self):
        """Test coordinator with vision disabled."""
        config = ScreenStateConfig(enable_vision_detection=False)
        coordinator = ScreenStateCoordinator(config=config)
        
        assert coordinator.detector is not None
        assert coordinator.detector.vision_agent is None
    
    def test_ocr_disabled(self):
        """Test coordinator with OCR disabled."""
        config = ScreenStateConfig(enable_ocr=False)
        coordinator = ScreenStateCoordinator(config=config)
        
        assert coordinator.text_detector is not None
    
    def test_action_logging_disabled(self):
        """Test coordinator with action logging disabled."""
        config = ScreenStateConfig(enable_action_logging=False)
        coordinator = ScreenStateCoordinator(config=config)
        
        # Action logger still created but disabled
        assert coordinator.action_logger is not None
    
    def test_recovery_disabled(self):
        """Test coordinator with recovery disabled."""
        config = ScreenStateConfig(recovery_enabled=False)
        coordinator = ScreenStateCoordinator(config=config)
        
        assert coordinator.config.recovery_enabled is False


class TestCoordinatorEdgeCases:
    """Tests for edge cases."""
    
    def test_coordinator_multiple_creations(self):
        """Test creating multiple coordinators."""
        coord1 = ScreenStateCoordinator()
        coord2 = ScreenStateCoordinator()
        
        assert coord1 is not coord2
        assert coord1.detector is not coord2.detector
    
    def test_coordinator_cache_limit_respected(self):
        """Test that cache limits are respected."""
        config = ScreenStateConfig(max_cached_screenshots=3)
        coordinator = ScreenStateCoordinator(config=config)
        
        for i in range(5):
            coordinator.screenshot_cache.add(f"img{i}".encode())
        
        assert coordinator.screenshot_cache.size() <= 3
