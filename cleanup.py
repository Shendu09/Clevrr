from __future__ import annotations

import shutil
from pathlib import Path


PROJECT_ROOT = Path(__file__).parent.resolve()


GITIGNORE_BLOCK = [
    "# Test databases (auto-generated)",
    "data/test_*.db",
    "data/test_*_*.db",
    "",
    "# Runtime screenshots",
    "data/screenshots/",
    "",
    "# Runtime solutions",
    "data/solutions/",
    "",
    "# Runtime logs",
    "data/logs/",
    "data/safety_log.txt",
    "",
    "# Runtime databases",
    "data/instincts.db",
    "data/memory.db",
    "",
    "# Python cache",
    "__pycache__/",
    "*.pyc",
    "*.pyo",
    "*.pyd",
    ".pytest_cache/",
    "*.egg-info/",
    "dist/",
    "build/",
    "",
    "# OS files",
    ".DS_Store",
    "Thumbs.db",
    "",
    "# IDE files",
    ".vscode/settings.json",
    ".idea/",
]


def _delete_file(path: Path, counters: dict[str, int]) -> None:
    if path.exists() and path.is_file():
        print(f"Deleting: {path.relative_to(PROJECT_ROOT)}")
        path.unlink()
        counters["files_deleted"] += 1
    else:
        print(f"Skipping (not found): {path.relative_to(PROJECT_ROOT)}")
        counters["skipped"] += 1


def _delete_folder(path: Path, counters: dict[str, int]) -> None:
    if path.exists() and path.is_dir():
        print(f"Deleting: {path.relative_to(PROJECT_ROOT)}/")
        shutil.rmtree(path)
        counters["folders_deleted"] += 1
    else:
        print(f"Skipping (not found): {path.relative_to(PROJECT_ROOT)}")
        counters["skipped"] += 1


def _delete_empty_folder(path: Path, counters: dict[str, int]) -> None:
    if not path.exists() or not path.is_dir():
        print(f"Skipping (not found): {path.relative_to(PROJECT_ROOT)}")
        counters["skipped"] += 1
        return

    if any(path.iterdir()):
        print(f"Skipping (not found): {path.relative_to(PROJECT_ROOT)} (not empty)")
        counters["skipped"] += 1
        return

    print(f"Deleting: {path.relative_to(PROJECT_ROOT)}/")
    path.rmdir()
    counters["folders_deleted"] += 1


def _update_gitignore(counters: dict[str, int]) -> None:
    gitignore_path = PROJECT_ROOT / ".gitignore"
    if not gitignore_path.exists():
        print(f"Skipping (not found): {gitignore_path.relative_to(PROJECT_ROOT)} (creating)")
        existing_lines: list[str] = []
    else:
        existing_lines = gitignore_path.read_text(encoding="utf-8").splitlines()

    existing_set = set(existing_lines)
    lines_to_add = [line for line in GITIGNORE_BLOCK if line not in existing_set]

    if not lines_to_add:
        print("Skipping (not found): .gitignore (already contains required entries)")
        counters["skipped"] += 1
        return

    print("Deleting: .gitignore (updating entries)")
    if existing_lines and existing_lines[-1] != "":
        existing_lines.append("")
    existing_lines.extend(lines_to_add)
    gitignore_path.write_text("\n".join(existing_lines) + "\n", encoding="utf-8")
    counters["files_deleted"] += 1


def main() -> None:
    counters = {
        "files_deleted": 0,
        "folders_deleted": 0,
        "skipped": 0,
    }

    try:
        data_dir = PROJECT_ROOT / "data"

        # STEP 1 — Delete all test database files in data/
        patterns = [
            "test_*.db",
            "test_*_*.db",
            "test_full_flow_memory.db",
            "test_planner_memory.db",
            "test_run_memory.db",
            "test_memory.db",
        ]
        seen: set[Path] = set()
        for pattern in patterns:
            for db_path in data_dir.glob(pattern):
                if db_path in seen:
                    continue
                seen.add(db_path)
                _delete_file(db_path, counters)

        # STEP 2 — Delete stray root-level test files
        root_files = [
            PROJECT_ROOT / "test_basic.py",
            PROJECT_ROOT / "test_full_flow.py",
            PROJECT_ROOT / "check_ollama.py",
            PROJECT_ROOT / "check_setup.py",
        ]
        for file_path in root_files:
            _delete_file(file_path, counters)

        # STEP 3 — Delete entire data/screenshots/ folder
        _delete_folder(PROJECT_ROOT / "data" / "screenshots", counters)

        # STEP 4 — Delete data/solutions/ folder
        _delete_folder(PROJECT_ROOT / "data" / "solutions", counters)

        # STEP 5 — Delete duplicate root-level security/ folder
        _delete_folder(PROJECT_ROOT / "security", counters)

        # STEP 6 — Delete empty folders
        for folder in ["amd", "cuda", "benchmarks"]:
            _delete_empty_folder(PROJECT_ROOT / folder, counters)

        # STEP 7 — Delete runtime data files
        runtime_files = [
            PROJECT_ROOT / "data" / "safety_log.txt",
            PROJECT_ROOT / "data" / "instincts.db",
            PROJECT_ROOT / "data" / "memory.db",
        ]
        for file_path in runtime_files:
            _delete_file(file_path, counters)

        # STEP 8 — Update .gitignore
        _update_gitignore(counters)

    except Exception as exc:
        print(f"FAILED: {exc}")

    print("\nCleanup complete!")
    print(f"Files deleted:   {counters['files_deleted']}")
    print(f"Folders deleted: {counters['folders_deleted']}")
    print(f"Skipped:         {counters['skipped']}")


if __name__ == "__main__":
    main()
