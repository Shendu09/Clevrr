from __future__ import annotations

import logging
import os
import signal
import subprocess
import sys
from pathlib import Path
from typing import Optional

from .base_service import ClevrrService, ServiceState
from .config import ServiceConfig
from core.security import SecurityGateway


SYSTEMD_UNIT = """
[Unit]
Description={description}
Documentation=https://github.com/Shendu09/clevrr-os
After=network.target
Wants=network.target

[Service]
Type=simple
ExecStart={python_bin} {script_path}
Restart=always
RestartSec={restart_delay}
User={user}
Group={user}
WorkingDirectory={work_dir}
StandardOutput=journal
StandardError=journal
SyslogIdentifier=clevrr
KillMode=mixed
TimeoutStopSec=30
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
"""

SYSTEMD_PATH = Path("/etc/systemd/system/clevrr.service")
SERVICE_USER = "clevrr"


class LinuxService(ClevrrService):
    def __init__(self, config: ServiceConfig, gateway: SecurityGateway) -> None:
        super().__init__(config, gateway)
        self.logger = logging.getLogger("clevrr.linux")

    def _platform_start(self) -> None:
        def _handle_sigterm(signum: int, frame: Optional[object]) -> None:
            _ = signum, frame
            self.logger.info("SIGTERM received — stopping service")
            self.stop()
            sys.exit(0)

        def _handle_sigint(signum: int, frame: Optional[object]) -> None:
            _ = signum, frame
            self.logger.info("SIGINT received — stopping service")
            self.stop()
            sys.exit(0)

        def _handle_sigusr1(signum: int, frame: Optional[object]) -> None:
            _ = signum, frame
            status = self.get_status()
            self.logger.info(
                f"SIGUSR1 status dump: "
                f"state={status.state.value} "
                f"pid={status.pid} "
                f"uptime={status.uptime_seconds:.0f}s "
                f"mem={status.memory_mb:.0f}MB "
                f"cpu={status.cpu_percent:.1f}%"
            )

        signal.signal(signal.SIGTERM, _handle_sigterm)
        signal.signal(signal.SIGINT, _handle_sigint)
        signal.signal(signal.SIGUSR1, _handle_sigusr1)
        self.logger.info("Linux signal handlers registered")

    def _platform_stop(self) -> None:
        sock = Path(self._config.ipc_socket_path)
        if sock.exists():
            try:
                sock.unlink()
                self.logger.debug(f"Cleaned up socket: {sock}")
            except Exception as exc:
                self.logger.warning(f"Could not remove socket: {exc}")

    def _platform_install(self) -> None:
        if os.geteuid() != 0:
            raise PermissionError(
                "Must run as root to install systemd service. "
                "Try: sudo python clevrr_service.py install"
            )

        result = subprocess.run(["id", SERVICE_USER], capture_output=True)
        if result.returncode != 0:
            subprocess.run(
                [
                    "useradd",
                    "--system",
                    "--no-create-home",
                    "--shell",
                    "/usr/sbin/nologin",
                    SERVICE_USER,
                ],
                capture_output=True,
                check=True,
            )
            self.logger.info(f"Created system user: {SERVICE_USER}")

        root_dir = Path(__file__).parent.parent.parent.resolve()
        unit_content = SYSTEMD_UNIT.format(
            description=self._config.description,
            python_bin=sys.executable,
            script_path=root_dir / "clevrr_service.py",
            restart_delay=self._config.restart_delay,
            user=SERVICE_USER,
            work_dir=root_dir,
        )

        SYSTEMD_PATH.write_text(unit_content.strip(), encoding="utf-8")
        self.logger.info(f"Written unit file: {SYSTEMD_PATH}")

        _run_cmd(["systemctl", "daemon-reload"])
        _run_cmd(["systemctl", "enable", "clevrr"])
        self.logger.info("systemd service enabled (starts on boot)")

    def _platform_uninstall(self) -> None:
        if os.geteuid() != 0:
            raise PermissionError("Must run as root to uninstall")

        _run_cmd(["systemctl", "stop", "clevrr"], check=False)
        _run_cmd(["systemctl", "disable", "clevrr"], check=False)

        if SYSTEMD_PATH.exists():
            SYSTEMD_PATH.unlink()
            self.logger.info(f"Removed unit file: {SYSTEMD_PATH}")

        _run_cmd(["systemctl", "daemon-reload"])
        self.logger.info("systemd service uninstalled")

    def run_foreground(self) -> None:
        self.start()
        self.logger.info("Running in foreground mode. Press Ctrl+C to stop.")
        try:
            signal.pause()
        except KeyboardInterrupt:
            pass
        finally:
            self.stop()


def _run_cmd(
    cmd: list[str],
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    logger = logging.getLogger("clevrr.linux")
    logger.debug(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if check and result.returncode != 0:
        raise RuntimeError(
            f"Command failed: {' '.join(cmd)}\n"
            f"stderr: {result.stderr.strip()}"
        )
    return result