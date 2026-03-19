"""Selective SKILL.md loader inspired by ECC skills loading."""

from __future__ import annotations

import glob
import os


class SkillsLoader:
    """Indexes skills and loads only relevant skill files on demand."""

    def __init__(self, skills_dir: str = "skills"):
        self.skills_dir = skills_dir
        self.loaded_skills = {}
        self.skill_index = {}
        self._index_skills()

    def _index_skills(self):
        if not os.path.exists(self.skills_dir):
            os.makedirs(self.skills_dir)
            return

        for skill_file in glob.glob(
            f"{self.skills_dir}/**/SKILL.md",
            recursive=True,
        ):
            skill_name = os.path.basename(os.path.dirname(skill_file))
            self.skill_index[skill_name] = skill_file

    def load_skill(self, skill_name: str) -> str | None:
        if skill_name in self.loaded_skills:
            return self.loaded_skills[skill_name]

        if skill_name not in self.skill_index:
            return None

        with open(self.skill_index[skill_name], encoding="utf-8") as file:
            content = file.read()

        self.loaded_skills[skill_name] = content
        return content

    def find_relevant_skill(self, task: str) -> str | None:
        task_lower = task.lower()

        skill_keywords = {
            "app_launch": ["open", "launch", "start", "run"],
            "file_operations": ["file", "folder", "document", "save"],
            "voice_commands": ["say", "voice", "speak", "tell"],
            "system_control": ["system", "settings", "control", "health", "cpu", "memory"],
            "browser_control": ["chrome", "browser", "website", "google", "search"],
        }

        for skill_name, keywords in skill_keywords.items():
            if any(keyword in task_lower for keyword in keywords):
                return self.load_skill(skill_name)

        return None

    def get_skill_list(self) -> list:
        return list(self.skill_index.keys())
