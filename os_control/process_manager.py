import psutil


class ProcessManager:

    def get_system_health(self) -> dict:
        return {
            "cpu_percent": psutil.cpu_percent(interval=0.2),
            "memory_percent": psutil.virtual_memory().percent,
        }
