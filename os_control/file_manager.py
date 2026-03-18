from pathlib import Path


class FileManager:

    def organize_downloads(self):
        downloads = Path.home() / "Downloads"
        if not downloads.exists():
            return

        mapping = {
            "Documents": {".pdf", ".doc", ".docx", ".txt", ".xlsx", ".pptx"},
            "Images": {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"},
            "Videos": {".mp4", ".mkv", ".avi", ".mov", ".wmv"},
            "Audio": {".mp3", ".wav", ".flac", ".m4a"},
            "Archives": {".zip", ".rar", ".7z", ".tar", ".gz"},
        }

        for file in downloads.iterdir():
            if not file.is_file():
                continue
            suffix = file.suffix.lower()
            for folder, exts in mapping.items():
                if suffix in exts:
                    target_dir = downloads / folder
                    target_dir.mkdir(exist_ok=True)
                    target_path = target_dir / file.name
                    if not target_path.exists():
                        file.rename(target_path)
                    break
