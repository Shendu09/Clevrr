from __future__ import annotations

import logging
import os
import sys
import time
import threading
from abc import ABC, abstractmethod
from logging.handlers import RotatingFileHandler
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

from .config import ServiceConfig

import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from core.security import SecurityGateway


class ServiceState(str, Enum):
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    ERROR = "error"


@dataclass(slots=True)
class ServiceInfo:
    state: ServiceState
    pid: int
    start_time: Optional[float]
    memory_mb: float = 0.0
    cpu_percent: float = 0.0
    uptime_seconds: float = 0.0


class ClevrrService(ABC):
    def __init__(self, config: ServiceConfig, gateway: SecurityGateway) -> None:
        self._config = config
        self._gateway = gateway
        self._state = ServiceState.STOPPED
        self._pid = os.getpid()
        self._start_time: Optional[float] = None
        self._lock = threading.Lock()
        self._health_monitor = None
        self._ipc_server = None
        self.logger = logging.getLogger("clevrr")
        self._setup_logging()

    @abstractmethod
    def _platform_start(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def _platform_stop(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def _platform_install(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def _platform_uninstall(self) -> None:
        raise NotImplementedError

    def start(self) -> None:
        with self._lock:
            if self._state == ServiceState.RUNNING:
                self.logger.warning("Service already running")
                return
            self._state = ServiceState.STARTING
            self._start_time = time.time()

        try:
            self.logger.info(f"Clevrr service starting (pid={self._pid})")
            self._platform_start()

            from .health_monitor import HealthMonitor
            from .ipc_server import IPCServer

            self._health_monitor = HealthMonitor(
                config=self._config,
                on_critical=self._on_health_critical,
            )
            self._ipc_server = IPCServer(config=self._config, gateway=self._gateway)

            self._health_monitor.start()
            self._ipc_server.start()

            with self._lock:
                self._state = ServiceState.RUNNING

            self.logger.info("Clevrr service started successfully")
        except Exception as exc:
            with self._lock:
                self._state = ServiceState.ERROR
            self.logger.error(f"Service failed to start: {exc}")
            raise

    def stop(self) -> None:
        with self._lock:
            if self._state == ServiceState.STOPPED:
                return
            self._state = ServiceState.STOPPING

        self.logger.info("Clevrr service stopping...")

        if self._health_monitor:
            self._health_monitor.stop()

        if self._ipc_server:
            self._ipc_server.stop()

        self._platform_stop()

        with self._lock:
            self._state = ServiceState.STOPPED
            self._start_time = None

        self.logger.info("Clevrr service stopped")

    def install(self) -> None:
        self.logger.info("Installing Clevrr service...")
        self._platform_install()
        self.logger.info("Clevrr service installed successfully")

    def uninstall(self) -> None:
        self.logger.info("Uninstalling Clevrr service...")
        self._platform_uninstall()
        self.logger.info("Clevrr service uninstalled")

    def get_status(self) -> ServiceInfo:
        with self._lock:
            state = self._state
            start_time = self._start_time

        uptime = 0.0
        if start_time:
            uptime = time.time() - start_time

        memory_mb = 0.0
        cpu_percent = 0.0
        try:
            import psutil

            proc = psutil.Process(self._pid)
            memory_mb = proc.memory_info().rss / 1024 / 1024
            cpu_percent = proc.cpu_percent(interval=0.1)
        except Exception:
            pass

        return ServiceInfo(
            state=state,
            pid=self._pid,
            start_time=start_time,
            memory_mb=round(memory_mb, 1),
            cpu_percent=round(cpu_percent, 1),
            uptime_seconds=round(uptime, 1),
        )

    def is_running(self) -> bool:
        with self._lock:
            return self._state == ServiceState.RUNNING

    def _on_health_critical(self, status) -> None:
        self.logger.error(
            f"Health critical: {status.warnings}. "
            f"Memory={status.memory_mb:.0f}MB "
            f"CPU={status.cpu_percent:.1f}%"
        )
        if self._config.auto_restart:
            self.logger.warning(f"Auto-restart in {self._config.restart_delay}s...")
            threading.Timer(self._config.restart_delay, self._auto_restart).start()

    def _auto_restart(self) -> None:
        self.logger.info("Performing auto-restart...")
        try:
            self.stop()
            time.sleep(1)
            self.start()
            self.logger.info("Auto-restart successful")
        except Exception as exc:
            self.logger.error(f"Auto-restart failed: {exc}")
            with self._lock:
                self._state = ServiceState.ERROR

    def _setup_logging(self) -> None:
        self._config.log_dir.mkdir(parents=True, exist_ok=True)
        log_file = self._config.log_dir / "clevrr.log"

        self.logger = logging.getLogger("clevrr")
        self.logger.setLevel(getattr(logging, self._config.log_level, logging.INFO))

        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setFormatter(
            logging.Formatter(
                "%(asctime)s [%(levelname)s] %(name)s — %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )

        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))

        if not self.logger.handlers:
            self.logger.addHandler(file_handler)
            self.logger.addHandler(console_handler)