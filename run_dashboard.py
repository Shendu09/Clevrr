from __future__ import annotations

import sys
import threading
import time
import webbrowser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from dashboard.app import app


def open_browser() -> None:
    time.sleep(1.5)
    webbrowser.open("http://localhost:5000")


if __name__ == "__main__":
    print("\n  Clevrr-OS Dashboard")
    print("  ─────────────────────────────")
    print("  http://localhost:5000")
    print("  Ctrl+C to stop\n")
    threading.Thread(target=open_browser, daemon=True).start()
    app.run(debug=False, port=5000, host="0.0.0.0")
