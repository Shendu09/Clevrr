from __future__ import annotations

import os
import platform
import socket
import struct
import threading
from typing import Callable, Optional

from .message import BusMessage

UNIX_SOCKET_PATH = "/tmp/clevrr_bus.sock"
WIN_PIPE_NAME = r"\\.\pipe\clevrr_bus"
TCP_HOST = "127.0.0.1"
TCP_PORT = 37655
HEADER_SIZE = 4
MAX_MSG_SIZE = 1024 * 1024
RECV_BUFFER = 65536


def frame(data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + data


def _recv_exact(sock: socket.socket, n: int) -> Optional[bytes]:
    buf = bytearray()
    while len(buf) < n:
        chunk = sock.recv(min(n - len(buf), RECV_BUFFER))
        if not chunk:
            return None
        buf.extend(chunk)
    return bytes(buf)


def recv_framed(sock: socket.socket) -> Optional[bytes]:
    header = _recv_exact(sock, HEADER_SIZE)
    if not header:
        return None
    length = struct.unpack(">I", header)[0]
    if length > MAX_MSG_SIZE:
        raise ValueError(f"Message too large: {length}")
    return _recv_exact(sock, length)


class TransportServer:
    def __init__(
        self,
        on_message: Callable[[BusMessage, socket.socket], None],
    ) -> None:
        self._on_message = on_message
        self._is_windows = platform.system() == "Windows"
        self._stop_event = threading.Event()
        self._server_sock: Optional[socket.socket] = None
        self._threads: list[threading.Thread] = []

    def start(self) -> None:
        if self._is_windows:
            try:
                import win32pipe

                _ = win32pipe
                thread_target = self._run_named_pipe
            except ImportError:
                thread_target = self._run_tcp_socket
        else:
            thread_target = self._run_unix_socket if hasattr(socket, "AF_UNIX") else self._run_tcp_socket

        t = threading.Thread(
            target=thread_target,
            name="clevrr-bus-transport",
            daemon=True,
        )
        self._threads.append(t)
        t.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._server_sock:
            try:
                self._server_sock.close()
            except Exception:
                pass
        if not self._is_windows and hasattr(socket, "AF_UNIX"):
            try:
                os.unlink(UNIX_SOCKET_PATH)
            except FileNotFoundError:
                pass

    def send(self, sock: socket.socket, msg: BusMessage) -> None:
        data = msg.to_bytes()
        framed = frame(data)

        if self._is_windows and not isinstance(sock, socket.socket):
            try:
                import win32file

                win32file.WriteFile(sock, framed)
                return
            except ImportError as exc:
                raise RuntimeError("pywin32 is required for Windows named pipes") from exc

        sock.sendall(framed)

    def _run_unix_socket(self) -> None:
        try:
            os.unlink(UNIX_SOCKET_PATH)
        except FileNotFoundError:
            pass

        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(UNIX_SOCKET_PATH)
        os.chmod(UNIX_SOCKET_PATH, 0o600)
        server.listen(10)
        server.settimeout(1.0)
        self._server_sock = server

        while not self._stop_event.is_set():
            try:
                conn, _ = server.accept()
                try:
                    conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                except OSError:
                    pass
                t = threading.Thread(
                    target=self._handle_client,
                    args=(conn,),
                    daemon=True,
                )
                self._threads.append(t)
                t.start()
            except socket.timeout:
                continue
            except OSError:
                if self._stop_event.is_set():
                    break

    def _run_tcp_socket(self) -> None:
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((TCP_HOST, TCP_PORT))
        server.listen(10)
        server.settimeout(1.0)
        self._server_sock = server

        while not self._stop_event.is_set():
            try:
                conn, _ = server.accept()
                conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                t = threading.Thread(
                    target=self._handle_client,
                    args=(conn,),
                    daemon=True,
                )
                self._threads.append(t)
                t.start()
            except socket.timeout:
                continue
            except OSError:
                if self._stop_event.is_set():
                    break

    def _run_named_pipe(self) -> None:
        try:
            import win32file
            import win32pipe
        except ImportError:
            return

        while not self._stop_event.is_set():
            try:
                pipe = win32pipe.CreateNamedPipe(
                    WIN_PIPE_NAME,
                    win32pipe.PIPE_ACCESS_DUPLEX,
                    win32pipe.PIPE_TYPE_BYTE
                    | win32pipe.PIPE_READMODE_BYTE
                    | win32pipe.PIPE_WAIT,
                    win32pipe.PIPE_UNLIMITED_INSTANCES,
                    MAX_MSG_SIZE,
                    MAX_MSG_SIZE,
                    0,
                    None,
                )
                win32pipe.ConnectNamedPipe(pipe, None)
                t = threading.Thread(
                    target=self._handle_pipe_client,
                    args=(pipe,),
                    daemon=True,
                )
                self._threads.append(t)
                t.start()
            except Exception:
                if self._stop_event.is_set():
                    break

    def _handle_pipe_client(self, pipe: object) -> None:
        try:
            import win32file
            import win32pipe

            while not self._stop_event.is_set():
                _, header = win32file.ReadFile(pipe, HEADER_SIZE)
                if not header or len(header) < HEADER_SIZE:
                    break
                length = struct.unpack(">I", header)[0]
                if length > MAX_MSG_SIZE:
                    break
                _, payload = win32file.ReadFile(pipe, length)
                if not payload:
                    break
                msg = BusMessage.from_bytes(payload)
                self._on_message(msg, pipe)  # type: ignore[arg-type]
        except Exception:
            pass
        finally:
            try:
                import win32file
                import win32pipe

                win32pipe.DisconnectNamedPipe(pipe)
                win32file.CloseHandle(pipe)
            except Exception:
                pass

    def _handle_client(self, conn: socket.socket) -> None:
        while not self._stop_event.is_set():
            try:
                data = recv_framed(conn)
                if data is None:
                    break
                msg = BusMessage.from_bytes(data)
                self._on_message(msg, conn)
            except Exception:
                break
        conn.close()
