# Adapted from OpenClaw (https://github.com/openclaw/openclaw)
# Production-ready gateway method handlers

from abc import ABC, abstractmethod
from typing import Any, Callable, Optional, Dict
import logging
import inspect

logger = logging.getLogger(__name__)


class ErrorCode:
    """Adapted from OpenClaw's ErrorCodes"""
    INVALID_REQUEST = "INVALID_REQUEST"
    UNAVAILABLE = "UNAVAILABLE"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    NOT_FOUND = "NOT_FOUND"
    INTERNAL = "INTERNAL"


class Response:
    """Structured response matching OpenClaw's respond() pattern"""
    
    def __init__(self, success: bool, data: Optional[Dict] = None, error: Optional[Dict] = None):
        self.success = success
        self.data = data or {}
        self.error = error
    
    def to_dict(self) -> Dict:
        if self.success:
            return {"success": True, **self.data}
        return {"success": False, "error": self.error}


class GatewayMethodHandlers(ABC):
    """
    Base class for gateway method handlers
    Exact pattern from OpenClaw's voicewakeHandlers and similar
    From: src/gateway/server-methods/voicewake.ts
    """
    
    @abstractmethod
    def get_method_map(self) -> Dict[str, Callable]:
        """Return method name -> handler mapping"""
        pass


class VoiceWakeHandlers(GatewayMethodHandlers):
    """
    Exact adaptation of OpenClaw's voicewakeHandlers
    From: src/gateway/server-methods/voicewake.ts
    """
    
    def __init__(self, config_manager):
        self.config_manager = config_manager
    
    def get_method_map(self) -> Dict[str, Callable]:
        return {
            "voicewake.get": self.handle_get,
            "voicewake.set": self.handle_set,
        }
    
    async def handle_get(self, params: Dict, context: Any) -> Response:
        """voicewake.get - fetch current triggers"""
        try:
            cfg = self.config_manager.get()
            return Response(True, {"triggers": cfg.triggers})
        except Exception as err:
            logger.exception("voicewake.get failed")
            return Response(False, error={
                "code": ErrorCode.UNAVAILABLE,
                "message": str(err)
            })
    
    async def handle_set(self, params: Dict, context: Any) -> Response:
        """voicewake.set - update wake word triggers"""
        triggers = params.get("triggers")
        
        if not isinstance(triggers, list):
            return Response(False, error={
                "code": ErrorCode.INVALID_REQUEST,
                "message": "voicewake.set requires triggers: string[]"
            })
        
        try:
            cfg = self.config_manager.set(triggers)
            # Broadcast change to all clients (would implement via context.broadcast)
            if hasattr(context, 'broadcast_voice_wake_changed'):
                context.broadcast_voice_wake_changed(cfg.triggers)
            return Response(True, {"triggers": cfg.triggers})
        except Exception as err:
            logger.exception("voicewake.set failed")
            return Response(False, error={
                "code": ErrorCode.UNAVAILABLE,
                "message": str(err)
            })


class GatewayMethodDispatcher:
    """
    Method dispatcher matching OpenClaw's approach
    Routes incoming method calls to appropriate handlers
    From: src/gateway/server-methods.ts pattern
    """
    
    def __init__(self):
        self.handlers: Dict[str, Callable] = {}
        self.handler_objects: Dict[str, GatewayMethodHandlers] = {}
    
    def register_handlers(self, namespace: str, handler_obj: GatewayMethodHandlers) -> None:
        """Register all methods from a handler object"""
        self.handler_objects[namespace] = handler_obj
        method_map = handler_obj.get_method_map()
        for method_name, handler in method_map.items():
            self.handlers[method_name] = handler
    
    async def dispatch(
        self,
        method: str,
        params: Dict[str, Any],
        context: Any = None
    ) -> Response:
        """
        Dispatch RPC method call
        Returns Response object
        """
        if method not in self.handlers:
            return Response(False, error={
                "code": ErrorCode.NOT_FOUND,
                "message": f"Method not found: {method}"
            })
        
        handler = self.handlers[method]
        
        try:
            if inspect.iscoroutinefunction(handler):
                response = await handler(params, context)
            else:
                response = handler(params, context)
            
            if isinstance(response, Response):
                return response
            
            # Assume handler returned dict directly
            return Response(True, response)
        
        except TypeError as e:
            logger.warning(f"Invalid parameters for {method}: {e}")
            return Response(False, error={
                "code": ErrorCode.INVALID_REQUEST,
                "message": f"Invalid parameters: {e}"
            })
        except Exception as e:
            logger.exception(f"Handler error for {method}")
            return Response(False, error={
                "code": ErrorCode.INTERNAL,
                "message": "Internal server error"
            })


# Example usage
async def example():
    from core.voice.voicewake_config import VoiceWakeConfigManager
    
    # Initialize
    config_mgr = VoiceWakeConfigManager("/config")
    handlers = VoiceWakeHandlers(config_mgr)
    dispatcher = GatewayMethodDispatcher()
    dispatcher.register_handlers("voicewake", handlers)
    
    # Dispatch method
    response = await dispatcher.dispatch(
        "voicewake.get",
        {},
        context=None
    )
    print(response.to_dict())
