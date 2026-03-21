from __future__ import annotations

import json
import logging
import os
import platform
import socket
import threading
from dataclasses import dataclass, field
from typing import Optional

from .config import ServiceConfig
from core.security import SecurityGateway


MAX_MESSAGE_BYTES = 65536
SOCKET_TIMEOUT = 30.0
BACKLOG = 5


@dataclass(slots=True)
class IPCRequest:
    action: str
    payload: dict
    request_id: str = ""


@dataclass(slots=True)
class IPCResponse:
    success: bool
    data: dict = field(default_factory=dict)
    error: Optional[str] = None
    request_id: str = ""

    def to_bytes(self) -> bytes:
        return json.dumps(
            {
                "success": self.success,
                "data": self.data,
                "error": self.error,
                "request_id": self.request_id,
            }
        ).encode("utf-8")


class IPCServer:
    def __init__(self, config: ServiceConfig, gateway: SecurityGateway) -> None:
        self._config = config
        self._gateway = gateway
        self._is_windows = platform.system() == "Windows"
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._client_threads: list[threading.Thread] = []
        self.logger = logging.getLogger("clevrr.ipc")

    def start(self) -> None:
        self._stop_event.clear()
        target = self._run_windows if self._is_windows else self._run_unix
        self._thread = threading.Thread(target=target, name="clevrr-ipc", daemon=True)
        self._thread.start()
        self.logger.info(
            f"IPC server started "
            f"({'named pipe' if self._is_windows else 'unix socket'})"
        )

    def stop(self) -> None:
        self._stop_event.set()

        if not self._is_windows:
            try:
                sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                sock.connect(self._config.ipc_socket_path)
                sock.close()
            except Exception:
                pass

        if self._thread:
            self._thread.join(timeout=2)

        for thread in self._client_threads:
            thread.join(timeout=2)

        if not self._is_windows:
            try:
                os.unlink(self._config.ipc_socket_path)
            except FileNotFoundError:
                pass

        self.logger.info("IPC server stopped")

    def _run_unix(self) -> None:
        sock_path = self._config.ipc_socket_path
        try:
            os.unlink(sock_path)
        except FileNotFoundError:
            pass

        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            server.bind(sock_path)
            os.chmod(sock_path, 0o600)
            server.listen(BACKLOG)
            server.settimeout(1.0)
            self.logger.info(f"Unix socket listening at {sock_path}")

            while not self._stop_event.is_set():
                try:
                    conn, _ = server.accept()
                    thread = threading.Thread(
                        target=self._handle_unix_client,
                        args=(conn,),
                        daemon=True,
                    )
                    self._client_threads.append(thread)
                    thread.start()
                except socket.timeout:
                    continue
                except Exception as exc:
                    if not self._stop_event.is_set():
                        self.logger.error(f"Accept error: {exc}")
        finally:
            server.close()

    def _run_windows(self) -> None:
        try:
            import win32pipe

            pipe_name = self._config.ipc_pipe_name
            self.logger.info(f"Named pipe listening at {pipe_name}")

            while not self._stop_event.is_set():
                try:
                    pipe = win32pipe.CreateNamedPipe(
                        pipe_name,
                        win32pipe.PIPE_ACCESS_DUPLEX,
                        win32pipe.PIPE_TYPE_MESSAGE
                        | win32pipe.PIPE_READMODE_MESSAGE
                        | win32pipe.PIPE_WAIT,
                        win32pipe.PIPE_UNLIMITED_INSTANCES,
                        MAX_MESSAGE_BYTES,
                        MAX_MESSAGE_BYTES,
                        0,
                        None,
                    )
                    win32pipe.ConnectNamedPipe(pipe, None)
                    thread = threading.Thread(
                        target=self._handle_windows_client,
                        args=(pipe,),
                        daemon=True,
                    )
                    self._client_threads.append(thread)
                    thread.start()
                except Exception as exc:
                    if not self._stop_event.is_set():
                        self.logger.error(f"Pipe error: {exc}")
        except ImportError:
            self.logger.error("pywin32 not installed — IPC unavailable on Windows")

    def _handle_unix_client(self, conn: socket.socket) -> None:
        try:
            conn.settimeout(SOCKET_TIMEOUT)
            raw = conn.recv(MAX_MESSAGE_BYTES)
            if not raw:
                return
            response = self._process_message(raw)
            conn.sendall(response.to_bytes())
        except socket.timeout:
            self.logger.warning("Client connection timed out")
        except Exception as exc:
            self.logger.error(f"Client handler error: {exc}")
        finally:
            conn.close()

    def _handle_windows_client(self, pipe: object) -> None:
        try:
            import win32file

            _, raw = win32file.ReadFile(pipe, MAX_MESSAGE_BYTES)
            response = self._process_message(raw)
            win32file.WriteFile(pipe, response.to_bytes())
        except Exception as exc:
            self.logger.error(f"Windows pipe handler error: {exc}")
        finally:
            try:
                import win32file
                import win32pipe

                win32pipe.DisconnectNamedPipe(pipe)
                win32file.CloseHandle(pipe)
            except Exception:
                pass

    def _process_message(self, raw: bytes) -> IPCResponse:
        try:
            msg = json.loads(raw.decode("utf-8"))
            action = msg.get("action", "")
            payload = msg.get("payload", {})
            request_id = msg.get("request_id", "")

            if action == "ping":
                return IPCResponse(True, {"pong": True}, None, request_id)

            if action == "status":
                return IPCResponse(
                    success=True,
                    data={"status": "running", "version": "2.0.0"},
                    error=None,
                    request_id=request_id,
                )

            if action == "scan":
                text = payload.get("text", "")
                if not text:
                    return self._error("scan requires payload.text", request_id)
                result = self._gateway.scan_text(text)
                return IPCResponse(
                    success=True,
                    data={
                        "safe": result.safe,
                        "level": result.level.value,
                        "threat_type": result.threat_type,
                        "matched_rule": result.matched_rule,
                    },
                    error=None,
                    request_id=request_id,
                )

            if action == "execute":
                user_id = payload.get("user_id", "")
                cmd_action = payload.get("action", "")
                target = payload.get("target", "")

                if not user_id or not cmd_action:
                    return self._error("execute requires user_id and action", request_id)

                if cmd_action == "read_file":
                    result = self._gateway.read_file(user_id, target)
                elif cmd_action == "write_file":
                    result = self._gateway.write_file(user_id, target, payload.get("content", ""))
                elif cmd_action == "run_command":
                    result = self._gateway.run_command(user_id, payload.get("command", []))
                elif cmd_action == "screenshot":
                    result = self._gateway.take_screenshot(user_id, target)
                else:
                    return self._error(f"Unknown execute action: {cmd_action}", request_id)

                return IPCResponse(
                    success=result.success,
                    data={"output": result.output, "exit_code": result.exit_code},
                    error=result.error,
                    request_id=request_id,
                )

            return self._error(f"Unknown action: {action}", request_id)
        except json.JSONDecodeError:
            return self._error("Invalid JSON message", "")
        except Exception as exc:
            self.logger.error(f"Message processing error: {exc}")
            return self._error(str(exc), "")

    def _error(self, message: str, request_id: str) -> IPCResponse:
        self.logger.warning(f"IPC error: {message}")
        return IPCResponse(success=False, data={}, error=message, request_id=request_id)