from __future__ import annotations

import logging
import os
import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Optional

from .config import ServiceConfig


@dataclass(slots=True)
class HealthStatus:
    timestamp: float
    memory_mb: float
    cpu_percent: float
    is_healthy: bool
    warnings: list[str] = field(default_factory=list)

    def summary(self) -> str:
        status = "healthy" if self.is_healthy else "unhealthy"
        return (
            f"[{status.upper()}] "
            f"RAM={self.memory_mb:.0f}MB "
            f"CPU={self.cpu_percent:.1f}% "
            f"warnings={self.warnings}"
        )


class HealthMonitor:
    def __init__(
        self,
        config: ServiceConfig,
        on_critical: Callable[[HealthStatus], None],
    ) -> None:
        self._config = config
        self._on_critical = on_critical
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._last_status: Optional[HealthStatus] = None
        self._lock = threading.Lock()
        self._consecutive_failures: int = 0
        self._max_failures: int = 3
        self.logger = logging.getLogger("clevrr.health")

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._monitor_loop,
            name="clevrr-health",
            daemon=True,
        )
        self._thread.start()
        self.logger.info("Health monitor started")

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=10)
        self.logger.info("Health monitor stopped")

    def get_status(self) -> Optional[HealthStatus]:
        with self._lock:
            return self._last_status

    def is_healthy(self) -> bool:
        with self._lock:
            if self._last_status is None:
                return True
            return self._last_status.is_healthy

    def _monitor_loop(self) -> None:
        self.logger.debug("Health monitor loop running")
        while not self._stop_event.is_set():
            try:
                status = self._check_health()
                with self._lock:
                    self._last_status = status

                if status.is_healthy:
                    self._consecutive_failures = 0
                    self.logger.debug(status.summary())
                else:
                    self._consecutive_failures += 1
                    self.logger.warning(
                        f"Health check failed ({self._consecutive_failures}/"
                        f"{self._max_failures}): {status.warnings}"
                    )
                    if self._consecutive_failures >= self._max_failures:
                        self.logger.error(
                            "Max consecutive health failures reached. "
                            "Triggering critical callback."
                        )
                        self._consecutive_failures = 0
                        try:
                            self._on_critical(status)
                        except Exception as exc:
                            self.logger.error(f"Critical callback failed: {exc}")

            except Exception as exc:
                self.logger.error(f"Health check error: {exc}")

            self._stop_event.wait(timeout=self._config.health_check_interval)

    def _check_health(self) -> HealthStatus:
        warnings: list[str] = []
        memory_mb = 0.0
        cpu_percent = 0.0

        try:
            import psutil

            proc = psutil.Process(os.getpid())

            memory_mb = proc.memory_info().rss / 1024 / 1024
            if memory_mb > self._config.max_memory_mb:
                warnings.append(
                    f"Memory {memory_mb:.0f}MB exceeds "
                    f"limit {self._config.max_memory_mb}MB"
                )

            cpu_percent = proc.cpu_percent(interval=1.0)
            if cpu_percent > self._config.max_cpu_percent:
                warnings.append(
                    f"CPU {cpu_percent:.1f}% exceeds "
                    f"limit {self._config.max_cpu_percent:.0f}%"
                )

            disk = psutil.disk_usage(str(self._config.data_dir.parent))
            disk_free_gb = disk.free / 1024 / 1024 / 1024
            if disk_free_gb < 0.5:
                warnings.append(f"Low disk space: {disk_free_gb:.2f}GB free")

        except ImportError:
            self.logger.warning("psutil not installed — health checks limited")
        except Exception as exc:
            warnings.append(f"Health check error: {exc}")

        return HealthStatus(
            timestamp=time.time(),
            memory_mb=round(memory_mb, 1),
            cpu_percent=round(cpu_percent, 1),
            is_healthy=len(warnings) == 0,
            warnings=warnings,
        )
