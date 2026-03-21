from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

from .base_service import ClevrrService, ServiceState
from .config import ServiceConfig
from core.security import SecurityGateway


SERVICE_NAME = "ClevrrAI"
SERVICE_DISPLAY_NAME = "Clevrr AI OS Layer"
SERVICE_DESCRIPTION = "Local AI layer for secure OS automation"
INSTALL_DIR = Path("C:/Program Files/Clevrr")


class WindowsService(ClevrrService):
    def __init__(
        self,
        config: ServiceConfig,
        gateway: SecurityGateway,
    ) -> None:
        super().__init__(config, gateway)
        self.logger = logging.getLogger("clevrr.windows")
        self._svc_stop_event = None

    def _platform_start(self) -> None:
        try:
            import win32event
            import win32service

            _ = win32service
            self._svc_stop_event = win32event.CreateEvent(None, 0, 0, None)
            self.logger.info("Windows service stop event created")
        except ImportError:
            self.logger.warning(
                "pywin32 not installed — "
                "running without SCM integration"
            )

        self.logger.info(f"Windows service starting (pid={os.getpid()})")

    def _platform_stop(self) -> None:
        try:
            import win32event

            if self._svc_stop_event:
                win32event.SetEvent(self._svc_stop_event)
                self.logger.debug("Windows stop event signalled")
        except ImportError:
            pass

        self.logger.info("Windows service stopping")

    def _platform_install(self) -> None:
        if not _is_admin():
            raise PermissionError(
                "Must run as Administrator to install Windows service.\n"
                "Right-click CMD → Run as Administrator, then retry."
            )

        try:
            import win32service
            import win32serviceutil

            script_path = str(Path(__file__).parent.parent.parent / "clevrr_service.py")
            _ = script_path
            win32serviceutil.InstallService(
                pythonClassString=f"{__name__}.WindowsService",
                serviceName=SERVICE_NAME,
                displayName=SERVICE_DISPLAY_NAME,
                description=SERVICE_DESCRIPTION,
                startType=win32service.SERVICE_AUTO_START,
                exeName=sys.executable,
            )

            _set_service_description(SERVICE_NAME, SERVICE_DESCRIPTION)
            _set_failure_actions(SERVICE_NAME, self._config.restart_delay)

            self.logger.info(
                f"Windows service '{SERVICE_NAME}' installed. "
                f"Start with: sc start {SERVICE_NAME}"
            )
        except ImportError:
            raise RuntimeError(
                "pywin32 required for Windows service installation.\n"
                "Run: pip install pywin32"
            )

    def _platform_uninstall(self) -> None:
        if not _is_admin():
            raise PermissionError("Must run as Administrator to uninstall")

        try:
            import win32serviceutil

            try:
                win32serviceutil.StopService(SERVICE_NAME)
                self.logger.info("Service stopped before uninstall")
            except Exception:
                pass

            win32serviceutil.RemoveService(SERVICE_NAME)
            self.logger.info(f"Windows service '{SERVICE_NAME}' removed")
        except ImportError:
            raise RuntimeError("pywin32 required. Run: pip install pywin32")

    def run_foreground(self) -> None:
        self.start()
        self.logger.info("Running in foreground mode. Press Ctrl+C to stop.")
        try:
            if self._svc_stop_event:
                try:
                    import win32con
                    import win32event

                    while True:
                        result = win32event.WaitForSingleObject(self._svc_stop_event, 1000)
                        if result == win32con.WAIT_OBJECT_0:
                            break
                except ImportError:
                    import time

                    while self.is_running():
                        time.sleep(1)
            else:
                import time

                while self.is_running():
                    time.sleep(1)
        except KeyboardInterrupt:
            self.logger.info("Ctrl+C received")
        finally:
            self.stop()


def _is_admin() -> bool:
    try:
        import ctypes

        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def _set_service_description(
    service_name: str,
    description: str,
) -> None:
    try:
        import winreg

        key_path = f"SYSTEM\\CurrentControlSet\\Services\\{service_name}"
        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            key_path,
            0,
            winreg.KEY_SET_VALUE,
        )
        winreg.SetValueEx(key, "Description", 0, winreg.REG_SZ, description)
        winreg.CloseKey(key)
    except Exception as exc:
        logging.getLogger("clevrr.windows").warning(
            f"Could not set service description: {exc}"
        )


def _set_failure_actions(
    service_name: str,
    restart_delay_secs: int,
) -> None:
    delay_ms = restart_delay_secs * 1000
    try:
        subprocess.run(
            [
                "sc",
                "failure",
                service_name,
                "reset=",
                "86400",
                "actions=",
                f"restart/{delay_ms}/restart/{delay_ms}/restart/{delay_ms}/",
            ],
            capture_output=True,
            check=False,
        )
    except Exception as exc:
        logging.getLogger("clevrr.windows").warning(
            f"Could not set failure actions: {exc}"
        )