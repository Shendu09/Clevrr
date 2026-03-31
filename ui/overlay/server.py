"""
Overlay WebSocket Server — Python ↔ Electron Communication

Runs a WebSocket server that:
- Accepts user queries from Electron overlay
- Routes queries through RouterService
- Sends drawing commands back to Electron
- Manages visual feedback (boxes, text, annotations)
"""

import asyncio
import json
import logging
import threading
from typing import Any, Dict, Optional, Set

import websockets

logger = logging.getLogger(__name__)


class OverlayServer:
    """
    WebSocket server for Electron overlay communication.
    
    Receives: {"type": "query", "query": "user input", ...}
    Sends: {"command": "draw_box", "id": "...", "x": ..., ...}
    """
    
    def __init__(self, host: str = "localhost", port: int = 9999):
        """
        Initialize the overlay server.

        Args:
            host: WebSocket server host.
            port: WebSocket server port.
        """
        self.host = host
        self.port = port
        self.is_running = False
        self.clients: Set[websockets.WebSocketServerProtocol] = set()
        self.router_service = None  # Will be set externally
        
        logger.info(f"[OVERLAY SERVER] Initialized on {host}:{port}")

    async def handle_client(self, websocket):
        """
        Handle a new client connection.

        Args:
            websocket: WebSocket connection.
        """
        client_id = f"{websocket.remote_address[0]}:{websocket.remote_address[1]}"
        self.clients.add(websocket)
        
        logger.info(f"[OVERLAY SERVER] Client connected: {client_id}")
        
        try:
            async for message in websocket:
                await self._process_message(websocket, message, client_id)
        
        except websockets.exceptions.ConnectionClosed:
            logger.info(f"[OVERLAY SERVER] Client disconnected: {client_id}")
        
        finally:
            self.clients.discard(websocket)

    async def _process_message(
        self, websocket: websockets.WebSocketServerProtocol, message: str, client_id: str
    ):
        """
        Process a message from the Electron overlay.

        Args:
            websocket: The client's WebSocket connection.
            message: The message string (JSON).
            client_id: ID of the client.
        """
        try:
            data = json.loads(message)
            msg_type = data.get("type", "unknown")
            
            logger.debug(f"[OVERLAY SERVER] Message from {client_id}: {msg_type}")
            
            if msg_type == "query":
                await self._handle_query(websocket, data, client_id)
            elif msg_type == "ping":
                await websocket.send(json.dumps({"type": "pong"}))
            else:
                logger.warning(f"[OVERLAY SERVER] Unknown message type: {msg_type}")
        
        except json.JSONDecodeError:
            logger.error(f"[OVERLAY SERVER] Invalid JSON from {client_id}: {message[:100]}")
        
        except Exception as e:
            logger.error(f"[OVERLAY SERVER] Error processing message: {e}")

    async def _handle_query(
        self, websocket: websockets.WebSocketServerProtocol, data: Dict[str, Any], client_id: str
    ):
        """
        Handle a user query from the overlay.

        Args:
            websocket: The client's WebSocket connection.
            data: The query data.
            client_id: ID of the client.
        """
        query = data.get("query", "").strip()
        if not query:
            return
        
        logger.info(f"[OVERLAY SERVER] Query from overlay: {query[:60]}...")
        
        # Send status: executing
        await self._broadcast({
            "command": "status",
            "text": "Routing request...",
            "color": "#4fc3f7",
        })
        
        # Route through RouterService
        if self.router_service:
            try:
                # Run router_service.handle_task() in a thread pool
                # (it's blocking and may take time)
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(
                    None, self.router_service.handle_task, query
                )
                
                # Log result
                action = result.get("action", "unknown")
                success = result.get("success", False)
                response = result.get("response", "Done")
                
                logger.info(
                    f"[OVERLAY SERVER] Routed to {action}: "
                    f"{'SUCCESS' if success else 'FAILED'}"
                )
                
                # Send result status
                status_text = response[:100] if response else "Task completed"
                status_color = "#4caf50" if success else "#f44336"
                
                await self._broadcast({
                    "command": "status",
                    "text": status_text,
                    "color": status_color,
                })
                
                # Draw completion indicator (optional animation)
                await self._broadcast({
                    "command": "draw_dot",
                    "id": "completion_dot",
                    "x": 100,
                    "y": 100,
                    "radius": 8,
                    "color": status_color,
                })
                
                # Clear after 3 seconds
                await asyncio.sleep(3)
                await self._broadcast({
                    "command": "clear",
                })
            
            except Exception as e:
                logger.error(f"[OVERLAY SERVER] Error handling query: {e}")
                await self._broadcast({
                    "command": "status",
                    "text": f"Error: {str(e)[:50]}",
                    "color": "#f44336",
                })
        else:
            logger.warning("[OVERLAY SERVER] RouterService not set")
            await self._broadcast({
                "command": "status",
                "text": "Backend not ready",
                "color": "#ff9800",
            })

    async def _broadcast(self, message: Dict[str, Any]):
        """
        Broadcast a message to all connected clients.

        Args:
            message: The message dictionary.
        """
        if not self.clients:
            logger.warning("[OVERLAY SERVER] No clients connected")
            return
        
        json_msg = json.dumps(message)
        logger.debug(f"[OVERLAY SERVER] Broadcasting: {message.get('command', 'unknown')}")
        
        # Send to all clients
        tasks = [client.send(json_msg) for client in self.clients]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def start(self):
        """Start the WebSocket server."""
        logger.info(f"[OVERLAY SERVER] Starting on ws://{self.host}:{self.port}")
        
        self.is_running = True
        
        async with websockets.serve(
            self.handle_client,
            self.host,
            self.port,
            ping_interval=20,
            ping_timeout=10,
        ):
            logger.info(f"[OVERLAY SERVER] Listening on ws://{self.host}:{self.port}")
            await asyncio.Future()  # Run forever

    def start_background(self):
        """Start the server in a background thread."""
        loop = asyncio.new_event_loop()
        
        def run_server():
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self.start())
            except Exception as e:
                logger.error(f"[OVERLAY SERVER] Error: {e}")
            finally:
                loop.close()
        
        thread = threading.Thread(target=run_server, daemon=True)
        thread.start()
        logger.info("[OVERLAY SERVER] Started in background thread")

    def set_router_service(self, router_service):
        """Set the RouterService instance."""
        self.router_service = router_service
        logger.info("[OVERLAY SERVER] RouterService set")


# Global server instance
_global_server: Optional[OverlayServer] = None


def get_overlay_server(host: str = "localhost", port: int = 9999) -> OverlayServer:
    """Get or create the global overlay server."""
    global _global_server
    if _global_server is None:
        _global_server = OverlayServer(host, port)
    return _global_server


if __name__ == "__main__":
    # Example: Run server standalone for testing
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s │ %(levelname)-8s │ %(name)-25s │ %(message)s",
    )
    
    server = OverlayServer()
    asyncio.run(server.start())
