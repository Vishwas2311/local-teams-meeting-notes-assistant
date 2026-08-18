"""Safe local file helpers."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from meeting_assistant.exceptions import StorageError


def atomic_write_text(path: Path, text: str) -> None:
    """Replace a text file atomically on the same filesystem."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(text, encoding="utf-8")
        os.replace(temporary, path)
    except OSError as exc:
        raise StorageError(f"Could not write {path}: {exc}") from exc


def atomic_write_json(path: Path, value: Any) -> None:
    atomic_write_text(path, json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n")


def ensure_writable(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    probe = directory / ".write-test"
    try:
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
    except OSError as exc:
        raise StorageError(f"Data directory is not writable: {directory}") from exc
