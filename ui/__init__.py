"""
Clevrr UI Components — Web and Desktop Interfaces

- dashboard.py: Original Gradio dashboard
- enhanced_dashboard.py: Real-time monitoring dashboard
- floating_ui.py: Floating overlay UI
- overlay/: Electron transparent overlay
"""

from .enhanced_dashboard import (
    create_dashboard_interface,
    launch_dashboard,
    DashboardState,
)

__all__ = [
    "create_dashboard_interface",
    "launch_dashboard",
    "DashboardState",
]
