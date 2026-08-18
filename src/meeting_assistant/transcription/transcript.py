"""Crash-resistant incremental transcript persistence."""

from __future__ import annotations

import json
import os
import threading
from collections.abc import Callable
from pathlib import Path

from meeting_assistant.models.schemas import TranscriptSegment
from meeting_assistant.utils.time import format_elapsed


class TranscriptWriter:
    """Append each segment to text and JSONL, flushing it before returning."""

    def __init__(self, directory: Path, on_line: Callable[[str], None] | None = None) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        self.text_path = directory / "transcript.txt"
        self.jsonl_path = directory / "transcript.jsonl"
        self._text = self.text_path.open("a", encoding="utf-8", buffering=1)
        self._jsonl = self.jsonl_path.open("a", encoding="utf-8", buffering=1)
        self._lock = threading.Lock()
        self._on_line = on_line

    def append(self, segment: TranscriptSegment) -> None:
        line = f"[{format_elapsed(segment.start_seconds)}] [{segment.source}] {segment.text}"
        with self._lock:
            self._text.write(line + "\n")
            self._jsonl.write(segment.model_dump_json() + "\n")
            self._text.flush()
            self._jsonl.flush()
            os.fsync(self._text.fileno())
            os.fsync(self._jsonl.fileno())
        if self._on_line:
            self._on_line(line)

    def close(self) -> None:
        with self._lock:
            if not self._text.closed:
                self._text.close()
            if not self._jsonl.closed:
                self._jsonl.close()

    def __enter__(self) -> TranscriptWriter:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


def load_segments(path: Path) -> list[TranscriptSegment]:
    if not path.exists():
        return []
    segments: list[TranscriptSegment] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            segments.append(TranscriptSegment.model_validate(json.loads(line)))
        except (json.JSONDecodeError, ValueError) as exc:
            raise ValueError(f"Malformed transcript JSONL at line {number}: {exc}") from exc
    return segments
