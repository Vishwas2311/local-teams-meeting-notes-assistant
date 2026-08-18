"""Queue consumer that isolates chunk failures."""

from __future__ import annotations

import logging
import queue
import threading
from pathlib import Path
from typing import Protocol

from meeting_assistant.audio.recorder import AudioChunk
from meeting_assistant.models.schemas import TranscriptSegment
from meeting_assistant.transcription.transcript import TranscriptWriter

LOGGER = logging.getLogger(__name__)


class Transcriber(Protocol):
    def transcribe(self, path: Path, source: str, offset: float) -> list[TranscriptSegment]: ...


class TranscriptionWorker(threading.Thread):
    def __init__(
        self,
        *,
        chunks: queue.Queue[AudioChunk | None],
        transcriber: Transcriber,
        writer: TranscriptWriter,
        keep_audio: bool,
        max_chunk_retries: int = 2,
    ) -> None:
        super().__init__(name="transcription-worker", daemon=True)
        self.chunks = chunks
        self.transcriber = transcriber
        self.writer = writer
        self.keep_audio = keep_audio
        self.max_chunk_retries = max_chunk_retries
        self.failures: list[str] = []

    def run(self) -> None:
        while True:
            chunk = self.chunks.get()
            try:
                if chunk is None:
                    return
                self._process(chunk)
            finally:
                self.chunks.task_done()

    def _process(self, chunk: AudioChunk) -> None:
        for attempt in range(self.max_chunk_retries + 1):
            try:
                for segment in self.transcriber.transcribe(
                    chunk.path, chunk.source, chunk.offset_seconds
                ):
                    self.writer.append(segment)
                if not self.keep_audio:
                    chunk.path.unlink(missing_ok=True)
                return
            except Exception as exc:
                LOGGER.warning(
                    "Chunk %s transcription attempt %d failed: %s",
                    chunk.path.name,
                    attempt + 1,
                    exc,
                )
        self.failures.append(chunk.path.name)
        LOGGER.error("Preserved failed audio chunk for recovery: %s", chunk.path)
