"""Instinct learning system inspired by ECC continuous-learning-v2."""

from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional


@dataclass
class Instinct:
    id: Optional[int] = None
    trigger: str = ""
    action: str = ""
    confidence: float = 0.0
    use_count: int = 0
    success_count: int = 0
    created_at: Optional[str] = None
    last_used: Optional[str] = None


class InstinctSystem:
    """Local instinct store and retrieval with confidence scoring."""

    def __init__(self, ollama_client, memory_system):
        self.ollama = ollama_client
        self.memory = memory_system
        self.instincts: list[Instinct] = []
        self.db_path = "data/instincts.db"
        self._init_db()
        self._load_instincts()

    def _connect(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        conn = self._connect()
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS instincts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trigger_text TEXT NOT NULL,
                action_text TEXT NOT NULL,
                action_type TEXT NOT NULL,
                confidence REAL DEFAULT 0.5,
                use_count INTEGER DEFAULT 0,
                success_count INTEGER DEFAULT 0,
                created_at TEXT,
                last_used TEXT,
                tags TEXT
            )
            """
        )
        conn.commit()
        conn.close()

    def _load_instincts(self):
        conn = self._connect()
        rows = conn.execute(
            """
            SELECT id, trigger_text, action_text,
                   confidence, use_count, success_count,
                   created_at, last_used
            FROM instincts
            ORDER BY confidence DESC
            """
        ).fetchall()
        conn.close()

        self.instincts = [
            Instinct(
                id=row[0],
                trigger=row[1],
                action=row[2],
                confidence=row[3] or 0.0,
                use_count=row[4] or 0,
                success_count=row[5] or 0,
                created_at=row[6],
                last_used=row[7],
            )
            for row in rows
        ]

    def extract_instinct(self, task: str, plan: dict, success: bool):
        """Extract and store a reusable instinct from a completed task."""
        if not task:
            return

        try:
            response = self.ollama.generate_json(
                prompt=f"""
                Task: "{task}"
                Steps taken: {plan.get('steps', [])}
                Succeeded: {success}

                Extract a reusable instinct from this.
                Reply in JSON:
                {{
                    "trigger": "short phrase that triggers this",
                    "action": "what to do when triggered",
                    "action_type": "app_launch|system|ai_task|file",
                    "confidence": 0.5,
                    "tags": ["tag1", "tag2"]
                }}
                """,
                system_prompt="JSON only. Be concise.",
            )
        except Exception:
            return

        if response and "trigger" in response and "action" in response:
            self.save_instinct(
                trigger=response["trigger"],
                action=response["action"],
                action_type=response.get("action_type", "ai_task"),
                confidence=0.5 if success else 0.2,
                tags=response.get("tags", []),
            )

    def save_instinct(self, trigger, action, action_type, confidence, tags=None):
        conn = self._connect()

        existing = conn.execute(
            "SELECT id, confidence, use_count FROM instincts WHERE trigger_text LIKE ?",
            (f"%{trigger[:20]}%",),
        ).fetchone()

        if existing:
            new_confidence = min(1.0, (existing[1] or 0.5) + 0.1)
            conn.execute(
                """
                UPDATE instincts
                SET confidence=?, use_count=use_count+1, last_used=?
                WHERE id=?
                """,
                (
                    new_confidence,
                    datetime.now().isoformat(),
                    existing[0],
                ),
            )
        else:
            conn.execute(
                """
                INSERT INTO instincts
                (trigger_text, action_text, action_type,
                 confidence, created_at, last_used, tags)
                VALUES (?,?,?,?,?,?,?)
                """,
                (
                    trigger,
                    action,
                    action_type,
                    confidence,
                    datetime.now().isoformat(),
                    datetime.now().isoformat(),
                    json.dumps(tags or []),
                ),
            )

        conn.commit()
        conn.close()
        self._load_instincts()

    def find_instinct(self, trigger: str) -> dict | None:
        conn = self._connect()
        rows = conn.execute(
            """
            SELECT id, trigger_text, action_text, action_type,
                   confidence, use_count
            FROM instincts
            WHERE confidence > 0.6
            ORDER BY confidence DESC
            """
        ).fetchall()
        conn.close()

        trigger_lower = trigger.lower()
        for row in rows:
            instinct_trigger = (row[1] or "").lower()
            if instinct_trigger and (
                instinct_trigger in trigger_lower
                or trigger_lower in instinct_trigger
            ):
                return {
                    "id": row[0],
                    "trigger": row[1],
                    "action": row[2],
                    "action_type": row[3],
                    "confidence": row[4],
                    "use_count": row[5],
                }
        return None

    def update_instinct_result(self, instinct_id: int, success: bool):
        conn = self._connect()

        if success:
            conn.execute(
                """
                UPDATE instincts
                SET success_count=success_count+1,
                    use_count=use_count+1,
                    confidence=MIN(1.0, confidence+0.05),
                    last_used=?
                WHERE id=?
                """,
                (datetime.now().isoformat(), instinct_id),
            )
        else:
            conn.execute(
                """
                UPDATE instincts
                SET use_count=use_count+1,
                    confidence=MAX(0.1, confidence-0.1),
                    last_used=?
                WHERE id=?
                """,
                (datetime.now().isoformat(), instinct_id),
            )

        conn.commit()
        conn.close()
        self._load_instincts()

    def get_all_instincts(self) -> list[dict[str, Any]]:
        conn = self._connect()
        rows = conn.execute(
            """
            SELECT trigger_text, action_text, action_type,
                   confidence, use_count
            FROM instincts
            ORDER BY confidence DESC
            """
        ).fetchall()
        conn.close()

        return [
            {
                "trigger": row[0],
                "action": row[1],
                "action_type": row[2],
                "confidence": row[3],
                "use_count": row[4],
            }
            for row in rows
        ]

    def export_instincts(self, path: str):
        instincts = self.get_all_instincts()
        with open(path, "w", encoding="utf-8") as file:
            json.dump(instincts, file, indent=2)
        print(f"Exported {len(instincts)} instincts to {path}")

    def import_instincts(self, path: str):
        with open(path, encoding="utf-8") as file:
            instincts = json.load(file)
        for instinct in instincts:
            self.save_instinct(
                trigger=instinct["trigger"],
                action=instinct["action"],
                action_type=instinct.get("action_type", "ai_task"),
                confidence=instinct.get("confidence", 0.5) * 0.8,
                tags=instinct.get("tags", []),
            )
        print(f"Imported {len(instincts)} instincts")

    def evolve_to_skills(self):
        instincts = self.get_all_instincts()
        high_conf = [
            instinct
            for instinct in instincts
            if instinct["confidence"] > 0.8 and instinct["use_count"] > 3
        ]

        groups = {}
        for instinct in high_conf:
            action_type = instinct.get("action_type", "general")
            if action_type not in groups:
                groups[action_type] = []
            groups[action_type].append(instinct)

        for skill_type, skill_instincts in groups.items():
            skill_dir = f"skills/{skill_type}"
            os.makedirs(skill_dir, exist_ok=True)

            skill_content = f"""---
name: {skill_type}
description: Auto-evolved from {len(skill_instincts)} instincts
confidence: high
auto_generated: true
---

# {skill_type.title()} Skill

## Learned Triggers
"""
            for instinct in skill_instincts:
                skill_content += (
                    f"\n- **{instinct['trigger']}** "
                    f"→ {instinct['action']} "
                    f"(confidence: {instinct['confidence']:.0%})"
                )

            with open(f"{skill_dir}/SKILL.md", "w", encoding="utf-8") as file:
                file.write(skill_content)

        return len(groups)

    def get_status(self) -> dict:
        all_instincts = self.get_all_instincts()
        return {
            "total": len(all_instincts),
            "high_confidence": sum(
                1 for instinct in all_instincts if instinct["confidence"] > 0.8
            ),
            "medium_confidence": sum(
                1
                for instinct in all_instincts
                if 0.5 < instinct["confidence"] <= 0.8
            ),
            "low_confidence": sum(
                1 for instinct in all_instincts if instinct["confidence"] <= 0.5
            ),
            "most_used": sorted(
                all_instincts,
                key=lambda instinct: instinct["use_count"],
                reverse=True,
            )[:5],
        }

    def clear_last_instinct(self) -> bool:
        conn = self._connect()
        row = conn.execute(
            "SELECT id FROM instincts ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if not row:
            conn.close()
            return False

        conn.execute("DELETE FROM instincts WHERE id = ?", (row[0],))
        conn.commit()
        conn.close()
        self._load_instincts()
        return True

    def save_manual_instinct(self, trigger: str, action: str = ""):
        if not trigger.strip():
            return
        self.save_instinct(
            trigger=trigger,
            action=action or trigger,
            action_type="ai_task",
            confidence=0.4,
            tags=["manual"],
        )
