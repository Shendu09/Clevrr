"""
Dashboard — Local Gradio Web Interface

Provides a local web UI at http://localhost:7860 for:
- Task input and execution
- Live status and progress tracking
- Screenshot preview
- Task history and memory stats
- System health monitoring

Runs entirely on localhost. No internet required.
"""

import logging
import os
import threading
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

import gradio as gr

if TYPE_CHECKING:
    from agents.orchestrator import Orchestrator
    from utils.voice_controller import VoiceController

logger = logging.getLogger(__name__)


def create_dashboard(
    orchestrator: "Orchestrator",
    voice_controller: Optional["VoiceController"] = None,
    config: Optional[dict] = None,
) -> gr.Blocks:
    """Create and configure the Gradio dashboard.

    Args:
        orchestrator: The main orchestrator instance.
        voice_controller: Optional voice controller for voice mode.
        config: UI configuration from settings.yaml.

    Returns:
        Configured Gradio Blocks app.
    """
    ui_config = (config or {}).get("ui", {})
    theme_name = ui_config.get("theme", "dark")
    refresh_interval = ui_config.get("refresh_interval", 1)

    # Select Gradio theme
    if theme_name == "dark":
        theme = gr.themes.Soft(
            primary_hue="blue",
            secondary_hue="slate",
            neutral_hue="slate",
        ).set(
            body_background_fill="*neutral_950",
            body_background_fill_dark="*neutral_950",
        )
    else:
        theme = gr.themes.Soft(primary_hue="blue")

    # ── State ─────────────────────────────────────────────────
    _task_thread: Optional[threading.Thread] = None

    # ── Handler Functions ─────────────────────────────────────

    def run_task(task_text: str) -> Tuple[str, str, str, str]:
        """Run a task and return status updates."""
        nonlocal _task_thread

        if not task_text or not task_text.strip():
            return (
                "⚠️ Please enter a task.",
                "Step 0 of 0",
                "0",
                "Idle",
            )

        # Run in background thread
        result_holder: Dict[str, Any] = {}

        def _run():
            result_holder["result"] = orchestrator.run_task(task_text.strip())

        _task_thread = threading.Thread(target=_run, daemon=True)
        _task_thread.start()

        return (
            f"🚀 Running: {task_text.strip()}",
            "Step 0 of ?",
            "0",
            "🔄 Running",
        )

    def cancel_task() -> Tuple[str, str]:
        """Cancel the running task."""
        msg = orchestrator.cancel_task()
        return msg, "⛔ Cancelled"

    def get_live_status() -> Tuple[str, str, float, str, Optional[str]]:
        """Get live status for auto-refresh."""
        status = orchestrator.get_status()

        task_name = status["current_task"] or "No task"
        step_info = f"Step {status['current_step']} of {status['total_steps']}"
        progress = status["progress_percent"]

        if status["is_running"]:
            badge = "🔄 Running"
        elif progress >= 100:
            badge = "✅ Complete"
        else:
            badge = "⏸ Idle"

        # Get latest screenshot
        screenshot_path = None
        try:
            screenshot_dir = orchestrator.screen.screenshot_dir
            if os.path.exists(screenshot_dir):
                files = sorted(
                    [
                        os.path.join(screenshot_dir, f)
                        for f in os.listdir(screenshot_dir)
                        if f.endswith(".png")
                    ],
                    key=os.path.getmtime,
                    reverse=True,
                )
                if files:
                    screenshot_path = files[0]
        except Exception:
            pass

        return task_name, step_info, progress, badge, screenshot_path

    def get_history_data() -> List[List[str]]:
        """Get task history for the dataframe."""
        episodes = orchestrator.get_history(limit=10)
        rows = []
        for ep in episodes:
            steps = ep.get("steps", [])
            step_count = len(steps) if isinstance(steps, list) else 0
            duration = ep.get("duration", 0)
            status_icon = "✅" if ep.get("success") else "❌"
            rows.append(
                [
                    ep.get("task", "?")[:60],
                    str(step_count),
                    f"{duration:.1f}s" if duration else "?",
                    status_icon,
                    ep.get("timestamp", "")[:19],
                ]
            )
        return rows

    def get_memory_stats() -> str:
        """Get formatted memory statistics."""
        stats = orchestrator.memory.get_stats()
        lines = [
            f"📊 **Memory Statistics**",
            f"",
            f"- **Total tasks remembered:** {stats['total_episodes']}",
            f"- **Overall success rate:** {stats['success_rate']}%",
            f"- **Knowledge entries:** {stats['total_knowledge']}",
            f"- **Procedures saved:** {stats['total_procedures']}",
        ]

        if stats["most_common_tasks"]:
            lines.append(f"")
            lines.append(f"**Most common tasks:**")
            for t in stats["most_common_tasks"][:3]:
                lines.append(f"  - {t['task'][:50]} (×{t['count']})")

        return "\n".join(lines)

    def get_system_status() -> str:
        """Get formatted system health status."""
        health = orchestrator.ollama.health_check()

        ollama_status = "✅ Connected" if health["connected"] else "❌ Not Running"
        vision_status = "✅ Loaded" if health["vision_model_ready"] else "⚠️ Missing"
        text_status = "✅ Loaded" if health["text_model_ready"] else "⚠️ Missing"

        voice_status = "✅ Enabled" if (
            voice_controller and voice_controller.enabled
        ) else "⏸ Disabled"

        response_time = (
            f"{health['response_time_ms']:.0f}ms"
            if health["response_time_ms"]
            else "N/A"
        )

        lines = [
            f"🖥️ **System Status**",
            f"",
            f"| Component | Status |",
            f"|-----------|--------|",
            f"| Ollama | {ollama_status} |",
            f"| Vision model (llava) | {vision_status} |",
            f"| Text model (llama3) | {text_status} |",
            f"| Voice | {voice_status} |",
            f"| Response time | {response_time} |",
        ]

        if health["models"]:
            lines.append(f"")
            lines.append(f"**Available models:**")
            for m in health["models"]:
                size_mb = m.get("size", 0) / (1024 * 1024)
                lines.append(f"  - {m['name']} ({size_mb:.0f} MB)")

        return "\n".join(lines)

    def toggle_voice(enabled: bool) -> str:
        """Toggle voice mode."""
        if voice_controller is None:
            return "Voice controller not initialized."

        if enabled:
            voice_controller.enabled = True
            voice_controller._load_whisper()
            voice_controller._load_tts()
            voice_controller.start_background_listening(
                lambda cmd: orchestrator.run_task(cmd)
            )
            return "🎤 Voice mode ENABLED. Say 'hey computer' to start."
        else:
            voice_controller.stop()
            return "🔇 Voice mode DISABLED."

    def get_performance_metrics() -> str:
        """Get performance and system metrics."""
        try:
            task_history = orchestrator.memory.get_all_episodes() if hasattr(orchestrator, 'memory') else []
            
            total_tasks = len(task_history)
            successful = sum(1 for t in task_history if t.get('success', False))
            failed = total_tasks - successful
            
            success_rate = (successful / total_tasks * 100) if total_tasks > 0 else 0
            
            lines = [
                "### 📈 Performance Metrics",
                "",
                f"| Metric | Value |",
                f"|--------|-------|",
                f"| Total Tasks | {total_tasks} |",
                f"| Successful | {successful} ({success_rate:.1f}%) |",
                f"| Failed | {failed} |",
                f"| Session Active | Started |",
            ]
            
            return "\n".join(lines)
        except Exception as e:
            logger.error(f"Error getting metrics: {e}")
            return "Could not load metrics."

    # ── Build the UI ──────────────────────────────────────────

    with gr.Blocks(
        title="Advanced Clevrr Computer — 100% Local AI",
        theme=theme,
        css="""
        .gradio-container { max-width: 1200px !important; }
        .status-badge { font-size: 1.2em; font-weight: bold; }
        """,
    ) as app:

        gr.Markdown(
            """
            # 🤖 Advanced Clevrr Computer
            ### 100% Local AI Agent — Zero APIs, Zero Cloud

            Control your computer with natural language.
            Everything runs locally on your machine.
            """
        )

        with gr.Row():
            # ── Left Column: Input & Control ──
            with gr.Column(scale=2):
                gr.Markdown("### 📝 Task Input")
                task_input = gr.Textbox(
                    label="What should I do?",
                    placeholder="e.g. Open Notepad and type 'Hello World'",
                    lines=2,
                    elem_id="task_input",
                )
                with gr.Row():
                    run_btn = gr.Button(
                        "▶ Run Task",
                        variant="primary",
                        elem_id="run_btn",
                    )
                    cancel_btn = gr.Button(
                        "⛔ Cancel",
                        variant="stop",
                        elem_id="cancel_btn",
                    )
                voice_toggle = gr.Checkbox(
                    label="🎤 Voice Mode",
                    value=False,
                    elem_id="voice_toggle",
                )
                voice_status = gr.Textbox(
                    label="Voice Status",
                    interactive=False,
                    elem_id="voice_status",
                )

            # ── Right Column: Live Status ──
            with gr.Column(scale=2):
                gr.Markdown("### 📊 Live Status")
                status_task = gr.Textbox(
                    label="Current Task",
                    interactive=False,
                    elem_id="status_task",
                )
                status_step = gr.Textbox(
                    label="Progress",
                    interactive=False,
                    elem_id="status_step",
                )
                status_progress = gr.Slider(
                    label="Completion",
                    minimum=0,
                    maximum=100,
                    value=0,
                    interactive=False,
                    elem_id="status_progress",
                )
                status_badge = gr.Textbox(
                    label="Status",
                    interactive=False,
                    value="⏸ Idle",
                    elem_id="status_badge",
                )

        with gr.Row():
            # ── Screenshot Preview ──
            with gr.Column(scale=2):
                gr.Markdown("### 🖼️ Live Screenshot")
                screenshot_img = gr.Image(
                    label="Current Screen",
                    type="filepath",
                    elem_id="screenshot_img",
                )
                refresh_btn = gr.Button(
                    "🔄 Refresh Screenshot",
                    elem_id="refresh_btn",
                )

            # ── Task History ──
            with gr.Column(scale=2):
                gr.Markdown("### 📜 Task History")
                history_df = gr.Dataframe(
                    headers=["Task", "Steps", "Duration", "Status", "Time"],
                    datatype=["str", "str", "str", "str", "str"],
                    label="Recent Tasks",
                    elem_id="history_df",
                )
                refresh_history_btn = gr.Button(
                    "🔄 Refresh History",
                    elem_id="refresh_history_btn",
                )

        with gr.Row():
            # ── Memory Stats ──
            with gr.Column():
                gr.Markdown("### 🧠 Memory")
                memory_md = gr.Markdown(
                    value="Click 'Refresh' to load stats.",
                    elem_id="memory_md",
                )
                refresh_memory_btn = gr.Button(
                    "🔄 Refresh Memory Stats",
                    elem_id="refresh_memory_btn",
                )

            # ── Performance Metrics ──
            with gr.Column():
                gr.Markdown("### 📈 Performance")
                metrics_md = gr.Markdown(
                    value="Click 'Refresh' to load metrics.",
                    elem_id="metrics_md",
                )
                refresh_metrics_btn = gr.Button(
                    "🔄 Refresh Metrics",
                    elem_id="refresh_metrics_btn",
                )

            # ── System Status ──
            with gr.Column():
                gr.Markdown("### ⚙️ System Health")
                system_md = gr.Markdown(
                    value="Click 'Refresh' to check system status.",
                    elem_id="system_md",
                )
                refresh_system_btn = gr.Button(
                    "🔄 Refresh System Status",
                    elem_id="refresh_system_btn",
                )

        # ── Event Handlers ────────────────────────────────────

        run_btn.click(
            fn=run_task,
            inputs=[task_input],
            outputs=[status_task, status_step, status_progress, status_badge],
        )

        cancel_btn.click(
            fn=cancel_task,
            outputs=[status_task, status_badge],
        )

        voice_toggle.change(
            fn=toggle_voice,
            inputs=[voice_toggle],
            outputs=[voice_status],
        )

        def refresh_screenshot():
            """Refresh the screenshot display."""
            _, _, _, _, path = get_live_status()
            return path

        refresh_btn.click(
            fn=refresh_screenshot,
            outputs=[screenshot_img],
        )

        refresh_history_btn.click(
            fn=get_history_data,
            outputs=[history_df],
        )

        refresh_memory_btn.click(
            fn=get_memory_stats,
            outputs=[memory_md],
        )

        refresh_metrics_btn.click(
            fn=get_performance_metrics,
            outputs=[metrics_md],
        )

        refresh_system_btn.click(
            fn=get_system_status,
            outputs=[system_md],
        )

        # Auto-refresh status with timer
        status_timer = gr.Timer(value=refresh_interval)
        status_timer.tick(
            fn=get_live_status,
            outputs=[
                status_task,
                status_step,
                status_progress,
                status_badge,
                screenshot_img,
            ],
        )

    return app


def launch_dashboard(
    orchestrator: "Orchestrator",
    voice_controller: Optional["VoiceController"] = None,
    config: Optional[dict] = None,
) -> None:
    """Create and launch the Gradio dashboard.

    Args:
        orchestrator: The main orchestrator instance.
        voice_controller: Optional voice controller.
        config: Full configuration dictionary.
    """
    ui_config = (config or {}).get("ui", {})
    port = ui_config.get("port", 7860)

    app = create_dashboard(orchestrator, voice_controller, config)

    print(
        f"\n🌐 Dashboard available at: http://localhost:{port}\n"
        f"   Press Ctrl+C to stop.\n"
    )

    app.launch(
        server_name="0.0.0.0",
        server_port=port,
        share=False,  # Local only, no sharing
        inbrowser=True,
    )
