from __future__ import annotations

import argparse
import json
import logging
import os
import platform
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from core.security import SecurityGateway, User, Role
from core.service import ServiceConfig, ConfigLoader, ServiceState


CONFIG_PATH = Path("./clevrr.ini")
VERSION = "2.0.0"
BANNER = """
   _____ _
  / ____| |
 | |    | | _____   ___ __ _ __
 | |    | |/ _ \\ \\ / / '__| '__|
 | |____| |  __/\\ V /| |  | |
  \\_____|_|\\___| \\_/ |_|  |_|

  AI-OS Security Layer v{version}
  Platform: {platform}
"""


def _load_service(config: ServiceConfig):
    gateway = SecurityGateway(data_dir=config.data_dir, dry_run=False)

    os_name = platform.system()
    if os_name == "Linux":
        from core.service.linux_service import LinuxService

        return LinuxService(config, gateway)
    if os_name == "Windows":
        from core.service.windows_service import WindowsService

        return WindowsService(config, gateway)
    raise RuntimeError(
        f"Unsupported platform: {os_name}. "
        f"Clevrr supports Windows and Linux only."
    )


def cmd_start(config: ServiceConfig) -> int:
    print(BANNER.format(version=VERSION, platform=platform.system()))
    service = _load_service(config)
    print(f"[*] Starting Clevrr service (pid={os.getpid()})")
    service.start()
    print("[+] Service started successfully")
    print(f"    IPC socket: {config.ipc_socket_path}")
    print(f"    Log dir:    {config.log_dir}")
    print(f"    Data dir:   {config.data_dir}")
    return 0


def cmd_stop(config: ServiceConfig) -> int:
    service = _load_service(config)
    print("[*] Stopping Clevrr service...")
    service.stop()
    print("[+] Service stopped")
    return 0


def cmd_install(config: ServiceConfig) -> int:
    service = _load_service(config)
    print("[*] Installing Clevrr as system service...")
    try:
        service.install()
        print("[+] Installation complete")
        if platform.system() == "Linux":
            print("    Start now:  sudo systemctl start clevrr")
            print("    Status:     sudo systemctl status clevrr")
            print("    Logs:       journalctl -u clevrr -f")
        else:
            from core.service.windows_service import SERVICE_NAME

            print(f"    Start now:  sc start {SERVICE_NAME}")
            print(f"    Status:     sc query {SERVICE_NAME}")
        return 0
    except PermissionError as exc:
        print(f"[!] Permission error: {exc}")
        return 1


def cmd_uninstall(config: ServiceConfig) -> int:
    service = _load_service(config)
    print("[*] Uninstalling Clevrr service...")
    try:
        service.uninstall()
        print("[+] Uninstalled successfully")
        return 0
    except PermissionError as exc:
        print(f"[!] Permission error: {exc}")
        return 1


def cmd_status(config: ServiceConfig) -> int:
    service = _load_service(config)
    status = service.get_status()
    print(
        json.dumps(
            {
                "state": status.state.value,
                "pid": status.pid,
                "uptime_seconds": status.uptime_seconds,
                "memory_mb": status.memory_mb,
                "cpu_percent": status.cpu_percent,
            },
            indent=2,
        )
    )
    return 0


def cmd_run(config: ServiceConfig) -> int:
    print(BANNER.format(version=VERSION, platform=platform.system()))
    print("[*] Running Clevrr in foreground (dev mode)")
    print("    Press Ctrl+C to stop\n")
    service = _load_service(config)
    service.run_foreground()
    return 0


def cmd_init(config_path: Path) -> int:
    config = ConfigLoader.default_config()
    ConfigLoader.save(config, config_path)
    print(f"[+] Created default config: {config_path}")
    print("    Edit it then run: python clevrr_service.py run")
    return 0


def main() -> int:
    logging.getLogger("clevrr").setLevel(logging.INFO)

    parser = argparse.ArgumentParser(
        prog="clevrr_service",
        description="Clevrr-OS AI Layer — Service Manager",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Commands:
  run        Run in foreground (development mode)
  start      Start as background service
  stop       Stop the running service
  install    Install as OS service (requires root/admin)
  uninstall  Remove OS service (requires root/admin)
  status     Show service health and status
  init       Create default config file

Examples:
  python clevrr_service.py init
  python clevrr_service.py run
  sudo python clevrr_service.py install
  sudo systemctl start clevrr
    """,
    )

    parser.add_argument(
        "command",
        choices=["run", "start", "stop", "install", "uninstall", "status", "init"],
        help="Command to execute",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=CONFIG_PATH,
        help=f"Path to config file (default: {CONFIG_PATH})",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"Clevrr-OS v{VERSION}",
    )

    args = parser.parse_args()
    config_path = args.config if args.config.is_absolute() else (Path(__file__).parent / args.config)

    if args.command == "init":
        return cmd_init(config_path)

    if config_path.exists():
        config = ConfigLoader.load(config_path)
    else:
        print(
            f"[!] Config not found at {config_path}. "
            f"Run 'init' first or using defaults."
        )
        config = ConfigLoader.default_config()

    commands = {
        "run": cmd_run,
        "start": cmd_start,
        "stop": cmd_stop,
        "install": cmd_install,
        "uninstall": cmd_uninstall,
        "status": cmd_status,
    }

    return commands[args.command](config)


if __name__ == "__main__":
    sys.exit(main())
