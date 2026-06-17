from __future__ import annotations

from pathlib import Path

import os

ROOT = Path(__file__).resolve().parents[1]

# Support Render persistent disk redirection via environment variables
DATA_DIR_ENV = os.environ.get("DATA_DIR")
if DATA_DIR_ENV:
    DATA_DIR = Path(DATA_DIR_ENV).resolve()
else:
    DATA_DIR = ROOT / "data"

KB_DIR = DATA_DIR / "knowledge_base"
UPLOAD_DIR = DATA_DIR / "uploads"
INDEX_DIR = DATA_DIR / "index"
ARTIFACTS_DIR = ROOT / "artifacts"


def ensure_directories() -> None:
    for directory in [DATA_DIR, KB_DIR, UPLOAD_DIR, INDEX_DIR, ARTIFACTS_DIR]:
        directory.mkdir(parents=True, exist_ok=True)


def save_bytes(filename: str, content: bytes, subdir: str = "uploads") -> Path:
    ensure_directories()
    target_dir = DATA_DIR / subdir
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / filename
    path.write_bytes(content)
    return path


def list_knowledge_files() -> list[Path]:
    ensure_directories()
    return [p for p in KB_DIR.iterdir() if p.suffix.lower() in {".txt", ".md", ".pdf", ".docx"}]
