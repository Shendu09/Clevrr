from __future__ import annotations

import os
import platform
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

from flask import Flask, jsonify, render_template, request

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.auth.config import AuthConfig
from core.auth.consent_manager import ConsentManager
from core.auth.token_vault import TokenVault
from core.brain.config import BrainConfig
from core.brain.intent_parser import IntentParser
from core.computer_use import AgentRegistry, ComputerUseConfig
from core.security import Role, SecurityGateway, User
from dashboard.live_tester import LiveTester

app = Flask(__name__)
START_TIME = time.time()

DATA_DIR = Path("./clevrr_data")
DATA_DIR.mkdir(exist_ok=True)

gateway = SecurityGateway(data_dir=DATA_DIR, dry_run=True)
auth_config = AuthConfig()
vault = TokenVault(auth_config)


def _add_user_safe(user: User) -> None:
    try:
        gateway.add_user(user)
    except Exception:
        pass


now = time.time()
_add_user_safe(User("alice", "Alice Admin", Role.ADMIN, created_at=now))
_add_user_safe(User("bob", "Bob User", Role.USER, created_at=now))
_add_user_safe(User("carol", "Carol Guest", Role.GUEST, created_at=now))
_add_user_safe(User("dave", "Dave Restricted", Role.RESTRICTED, created_at=now))

consent = ConsentManager()
consent.grant("alice", "google-oauth2", ["gmail.send", "gmail.readonly"], "user")
consent.grant("alice", "github", ["repo", "issues"], "user")
consent.grant("bob", "google-oauth2", ["calendar.events"], "user")

demo_entries = [
    ("alice", "send_email", True, "Email sent via Gmail", "boss@company.com"),
    ("alice", "create_issue", True, "GitHub issue created", "Shendu09/Clevrr"),
    ("bob", "delete_email", False, "Step-up auth denied by user", "inbox"),
    ("carol", "file_write", False, "Permission denied — Guest role", "C:/system32"),
    ("alice", "take_screenshot", True, "Screenshot saved", "data/screenshots/"),
    ("bob", "create_event", True, "Calendar event created", "calendar"),
    ("dave", "process_spawn", False, "Permission denied — Restricted", "cmd.exe"),
    ("alice", "read_file", True, "File read successfully", "README.md"),
    ("carol", "rm -rf /", False, "Threat blocked — CRITICAL", "/"),
    ("bob", "send_email", True, "Email sent via Gmail", "team@company.com"),
    ("alice", "brain:send_email", True, "AI Brain processed command", "send email to boss"),
    ("alice", "whatsapp_send", True, "WhatsApp message sent", "John"),
    ("bob", "leetcode_solve", True, "Solution written in Python", "Two Sum"),
    ("alice", "summarize_page", True, "Page summarized in 3 bullets", "arxiv.org"),
]
for uid, action, allowed, reason, target in demo_entries:
    gateway._audit.log(uid, action, allowed, reason, target)

brain_config = BrainConfig()
parser = IntentParser(brain_config)
cu_config = ComputerUseConfig()
registry = AgentRegistry(cu_config, gateway, "clevrr-agent")
tester = LiveTester(gateway, brain_config, cu_config)

AGENT_TASKS: list[dict] = []
AGENT_LOCK = threading.Lock()


@app.get("/")
def home():
    return render_template("dashboard.html")


@app.get("/favicon.ico")
def favicon():
    return ("", 204)


@app.get("/api/status")
def api_status():
    uptime = int(time.time() - START_TIME)
    hours = uptime // 3600
    minutes = (uptime % 3600) // 60
    entries = gateway._audit._entries
    blocked = [entry for entry in entries if not entry.allowed]
    return jsonify(
        {
            "service": "running",
            "version": "2.0.0",
            "phases_complete": 7,
            "tests_passing": 75,
            "uptime": f"{hours}h {minutes}m",
            "uptime_seconds": uptime,
            "audit_entries": len(entries),
            "threats_blocked": len(blocked),
            "active_users": 4,
            "connected_services": len(consent.list_all()),
            "auth0_domain": os.getenv("AUTH0_DOMAIN", "clevrr-os.us.auth0.com"),
            "platform": platform.system(),
            "ollama_model": brain_config.ollama_model,
            "vision_model": cu_config.vision_model,
            "agent_capabilities": registry.list_capabilities(),
            "agent_tasks_run": len(AGENT_TASKS),
        }
    )


@app.get("/api/audit")
def api_audit():
    entries = gateway._audit._entries[-50:]
    payload = [
        {
            "seq": entry.seq,
            "time": datetime.fromtimestamp(entry.timestamp).strftime("%H:%M:%S"),
            "user_id": entry.user_id,
            "action": entry.action,
            "allowed": entry.allowed,
            "reason": entry.reason,
            "target": entry.target or "",
        }
        for entry in reversed(entries)
    ]
    return jsonify(payload)


@app.get("/api/connections")
def api_connections():
    payload = [
        {
            "user_id": record.user_id,
            "service": record.service,
            "scopes": record.scopes,
            "granted_at": datetime.fromtimestamp(record.granted_at).strftime("%b %d %Y"),
            "granted_by": record.granted_by,
        }
        for record in consent.list_all()
    ]
    return jsonify(payload)


@app.get("/api/users")
def api_users():
    users = ["alice", "bob", "carol", "dave"]
    result = []
    for user_id in users:
        try:
            user = gateway.get_user(user_id)
            perms = gateway.list_permissions(user_id)
            result.append(
                {
                    "user_id": user.user_id,
                    "username": user.username,
                    "role": user.role.value,
                    "active": user.active,
                    "permissions": len(perms),
                    "connections": len(consent.list_for_user(user_id)),
                }
            )
        except Exception:
            pass
    return jsonify(result)


@app.post("/api/revoke")
def api_revoke():
    data = request.get_json(silent=True) or {}
    ok = consent.revoke(data.get("user_id", ""), data.get("service", ""))
    return jsonify({"success": ok})


@app.post("/api/command")
def api_command():
    data = request.get_json(silent=True) or {}
    command = str(data.get("command", "")).strip()
    user_id = str(data.get("user_id", "alice"))
    if not command:
        return jsonify({"response": "Enter a command"})

    intent = parser.parse(command)
    specialist = registry.get_agent(command)
    agent_name = specialist.__class__.__name__ if specialist else "GeneralBrain"

    gateway._audit.log(
        user_id,
        f"brain:{intent.intent}",
        intent.confidence > 0.5,
        f"Brain processed (conf={intent.confidence:.2f})",
        command[:50],
    )

    if intent.intent == "unknown":
        response = "I didn't understand that. Try: 'send whatsapp to John' or 'solve this leetcode problem'"
    else:
        response = (
            f"Understood: {intent.intent.replace('_', ' ').title()} via {intent.service} "
            f"({intent.confidence:.0%} confidence). Agent: {agent_name}. "
            "Auth0 Token Vault would provide credentials securely."
        )

    return jsonify(
        {
            "response": response,
            "intent": intent.intent,
            "service": intent.service,
            "confidence": round(intent.confidence * 100),
            "agent": agent_name,
            "parameters": intent.parameters,
        }
    )


@app.post("/api/agent/run")
def api_agent_run():
    data = request.get_json(silent=True) or {}
    goal = str(data.get("goal", "")).strip()
    dry_run = bool(data.get("dry_run", True))
    if not goal:
        return jsonify({"error": "Enter a goal"})

    specialist = registry.get_agent(goal)
    agent_name = specialist.__class__.__name__ if specialist else "GeneralLoop"

    with AGENT_LOCK:
        AGENT_TASKS.append(
            {
                "goal": goal,
                "agent": agent_name,
                "started_at": datetime.now().strftime("%H:%M:%S"),
                "status": "completed (dry run)",
            }
        )

    gateway._audit.log("clevrr-agent", f"computer_use:{agent_name}", True, f"Agent task: {goal[:50]}", goal[:50])

    return jsonify(
        {
            "success": True,
            "goal": goal,
            "agent": agent_name,
            "message": f"{agent_name} would execute: '{goal}'. In production this controls your screen.",
            "dry_run": dry_run,
        }
    )


@app.get("/api/agent/tasks")
def api_agent_tasks():
    with AGENT_LOCK:
        return jsonify(list(reversed(AGENT_TASKS[-20:])))


@app.post("/api/live/threat")
def api_live_threat():
    data = request.get_json(silent=True) or {}
    text = str(data.get("text", "")).strip()
    if not text:
        return jsonify({"error": "Enter text to scan"})
    return jsonify(tester.test_threat_detection(text))


@app.post("/api/live/brain")
def api_live_brain():
    data = request.get_json(silent=True) or {}
    command = str(data.get("command", "")).strip()
    if not command:
        return jsonify({"error": "Enter a command"})
    return jsonify(tester.test_brain_parsing(command))


@app.post("/api/live/chain")
def api_live_chain():
    return jsonify(tester.test_audit_chain())


@app.post("/api/live/rbac")
def api_live_rbac():
    data = request.get_json(silent=True) or {}
    user_id = str(data.get("user_id", "alice"))
    action = str(data.get("action", "file_read"))
    return jsonify(tester.test_rbac(user_id, action))


@app.post("/api/live/voice")
def api_live_voice():
    return jsonify(tester.test_voice())


@app.post("/api/live/agent")
def api_live_agent():
    data = request.get_json(silent=True) or {}
    goal = str(data.get("goal", "")).strip()
    dry_run = bool(data.get("dry_run", True))
    if not goal:
        return jsonify({"error": "Enter a goal"})
    return jsonify(tester.test_agent(goal, dry_run))


@app.post("/api/live/all")
def api_live_all():
    results = tester.test_all()
    return jsonify(
        {
            "results": results,
            "total": len(results),
            "passed": sum(1 for result in results if result.get("success")),
            "failed": sum(1 for result in results if not result.get("success")),
        }
    )


@app.get("/api/live/history")
def api_live_history():
    return jsonify(tester.get_history())


@app.get("/api/verify")
def api_verify():
    ok, message = gateway.verify_audit_chain()
    return jsonify({"intact": ok, "message": message, "entries": len(gateway._audit._entries)})


@app.get("/api/threat_scan")
def api_threat_scan():
    text = request.args.get("text", "")
    result = gateway.scan_text(text)
    return jsonify(
        {
            "safe": result.safe,
            "level": result.level.value,
            "threat_type": result.threat_type,
            "matched_rule": result.matched_rule,
        }
    )


if __name__ == "__main__":
    app.run(debug=True, port=5000, host="0.0.0.0")
