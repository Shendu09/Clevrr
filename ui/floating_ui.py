"""
FloatingUI — Minimal Always-On-Top Overlay

A small, draggable floating window that stays on top
of all other windows. Provides quick task input and
status display without switching to the full dashboard.

Uses tkinter — no external dependencies.
"""

import logging
import threading
import tkinter as tk
from tkinter import scrolledtext
from typing import Callable, Optional

logger = logging.getLogger(__name__)


class FloatingUI:
    """Minimal floating overlay for quick agent interaction.

    Provides:
    - Text input for commands
    - Status display
    - Always-on-top positioning
    - Draggable window
    """

    def __init__(
        self,
        on_task: Optional[Callable[[str], None]] = None,
        on_cancel: Optional[Callable[[], None]] = None,
    ) -> None:
        """Initialize the floating UI.

        Args:
            on_task: Callback when a task is submitted.
            on_cancel: Callback when cancel is pressed.
        """
        self.on_task = on_task
        self.on_cancel = on_cancel
        self._root: Optional[tk.Tk] = None
        self._status_var: Optional[tk.StringVar] = None
        self._thread: Optional[threading.Thread] = None

    def launch(self) -> None:
        """Launch the floating UI in a background thread."""
        self._thread = threading.Thread(target=self._build_ui, daemon=True)
        self._thread.start()

    def _build_ui(self) -> None:
        """Build and run the tkinter UI."""
        self._root = tk.Tk()
        self._root.title("Clevrr AI")
        self._root.geometry("350x200+50+50")
        self._root.attributes("-topmost", True)
        self._root.configure(bg="#1a1a2e")
        self._root.resizable(True, True)

        # Make window draggable
        self._root.bind("<Button-1>", self._start_drag)
        self._root.bind("<B1-Motion>", self._on_drag)

        # Title label
        title = tk.Label(
            self._root,
            text="🤖 Clevrr AI",
            font=("Segoe UI", 12, "bold"),
            bg="#1a1a2e",
            fg="#e94560",
        )
        title.pack(pady=(5, 2))

        # Input
        self._input = tk.Entry(
            self._root,
            font=("Segoe UI", 10),
            bg="#16213e",
            fg="white",
            insertbackground="white",
        )
        self._input.pack(padx=10, fill="x")
        self._input.bind("<Return>", lambda e: self._submit())

        # Buttons
        btn_frame = tk.Frame(self._root, bg="#1a1a2e")
        btn_frame.pack(pady=5)

        run_btn = tk.Button(
            btn_frame,
            text="▶ Run",
            command=self._submit,
            bg="#e94560",
            fg="white",
            font=("Segoe UI", 9, "bold"),
            relief="flat",
            padx=10,
        )
        run_btn.pack(side="left", padx=3)

        cancel_btn = tk.Button(
            btn_frame,
            text="⛔ Cancel",
            command=self._cancel,
            bg="#533483",
            fg="white",
            font=("Segoe UI", 9),
            relief="flat",
            padx=10,
        )
        cancel_btn.pack(side="left", padx=3)

        # Status
        self._status_var = tk.StringVar(value="⏸ Ready")
        status_label = tk.Label(
            self._root,
            textvariable=self._status_var,
            font=("Segoe UI", 9),
            bg="#1a1a2e",
            fg="#0f3460",
        )
        status_label.pack(pady=5)

        self._root.mainloop()

    def _submit(self) -> None:
        """Handle task submission."""
        text = self._input.get().strip()
        if text and self.on_task:
            self._input.delete(0, tk.END)
            self.update_status(f"🔄 Running: {text[:30]}...")
            threading.Thread(
                target=self.on_task, args=(text,), daemon=True
            ).start()

    def _cancel(self) -> None:
        """Handle cancel button."""
        if self.on_cancel:
            self.on_cancel()
        self.update_status("⛔ Cancelled")

    def update_status(self, status: str) -> None:
        """Update the status display.

        Args:
            status: Status text to display.
        """
        if self._status_var and self._root:
            try:
                self._root.after(0, self._status_var.set, status)
            except Exception:
                pass

    # Dragging support
    _drag_x = 0
    _drag_y = 0

    def _start_drag(self, event: tk.Event) -> None:
        self._drag_x = event.x
        self._drag_y = event.y

    def _on_drag(self, event: tk.Event) -> None:
        if self._root:
            x = self._root.winfo_x() + event.x - self._drag_x
            y = self._root.winfo_y() + event.y - self._drag_y
            self._root.geometry(f"+{x}+{y}")

    def close(self) -> None:
        """Close the floating UI."""
        if self._root:
            try:
                self._root.quit()
                self._root.destroy()
            except Exception:
                pass
