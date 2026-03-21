from __future__ import annotations

import configparser
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ServiceConfig:
    service_name: str = "clevrr"
    display_name: str = "Clevrr AI OS Layer"
    description: str = "Local AI layer for OS automation"
    data_dir: Path = field(default_factory=lambda: Path("./clevrr_data"))
    log_dir: Path = field(default_factory=lambda: Path("./clevrr_logs"))
    log_level: str = "INFO"
    ipc_socket_path: str = "/tmp/clevrr.sock"
    ipc_pipe_name: str = r"\\.\pipe\clevrr"
    health_check_interval: int = 30
    max_memory_mb: int = 512
    max_cpu_percent: float = 80.0
    auto_restart: bool = True
    restart_delay: int = 5


class ConfigLoader:
    @staticmethod
    def load(path: Path) -> ServiceConfig:
        parser = configparser.ConfigParser()
        parser.read(path)
        s = parser["service"] if "service" in parser else {}
        h = parser["health"] if "health" in parser else {}
        i = parser["ipc"] if "ipc" in parser else {}

        return ServiceConfig(
            service_name=s.get("name", "clevrr"),
            display_name=s.get("display_name", "Clevrr AI OS Layer"),
            description=s.get("description", "Local AI layer for OS automation"),
            data_dir=Path(s.get("data_dir", "./clevrr_data")),
            log_dir=Path(s.get("log_dir", "./clevrr_logs")),
            log_level=s.get("log_level", "INFO").upper(),
            ipc_socket_path=i.get("socket_path", "/tmp/clevrr.sock"),
            ipc_pipe_name=i.get("pipe_name", r"\\.\pipe\clevrr"),
            health_check_interval=int(h.get("interval", 30)),
            max_memory_mb=int(h.get("max_memory_mb", 512)),
            max_cpu_percent=float(h.get("max_cpu_percent", 80.0)),
            auto_restart=h.get("auto_restart", "true").lower() == "true",
            restart_delay=int(h.get("restart_delay", 5)),
        )

    @staticmethod
    def save(config: ServiceConfig, path: Path) -> None:
        parser = configparser.ConfigParser()
        parser["service"] = {
            "name": config.service_name,
            "display_name": config.display_name,
            "description": config.description,
            "data_dir": str(config.data_dir),
            "log_dir": str(config.log_dir),
            "log_level": config.log_level,
        }
        parser["health"] = {
            "interval": str(config.health_check_interval),
            "max_memory_mb": str(config.max_memory_mb),
            "max_cpu_percent": str(config.max_cpu_percent),
            "auto_restart": str(config.auto_restart).lower(),
            "restart_delay": str(config.restart_delay),
        }
        parser["ipc"] = {
            "socket_path": config.ipc_socket_path,
            "pipe_name": config.ipc_pipe_name,
        }

        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            parser.write(f)

    @staticmethod
    def default_config() -> ServiceConfig:
        return ServiceConfig()
