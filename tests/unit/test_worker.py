import queue
from pathlib import Path

import numpy as np

from meeting_assistant.audio.recorder import AudioChunk, write_wav
from meeting_assistant.models.schemas import TranscriptSegment
from meeting_assistant.transcription.transcript import TranscriptWriter
from meeting_assistant.transcription.worker import TranscriptionWorker


class FakeTranscriber:
    def transcribe(self, path: Path, source: str, offset: float) -> list[TranscriptSegment]:
        return [
            TranscriptSegment(
                start_seconds=offset, end_seconds=offset + 1, text="ok", source=source
            )
        ]


class FailingTranscriber:
    def transcribe(self, path: Path, source: str, offset: float) -> list[TranscriptSegment]:
        raise RuntimeError("model failure")


def test_worker_deletes_successful_chunk(tmp_path: Path) -> None:
    path = tmp_path / "chunk.wav"
    write_wav(path, np.ones(16000, dtype=np.float32) * 0.1)
    chunks: queue.Queue[AudioChunk | None] = queue.Queue()
    writer = TranscriptWriter(tmp_path / "meeting")
    worker = TranscriptionWorker(
        chunks=chunks, transcriber=FakeTranscriber(), writer=writer, keep_audio=False
    )
    worker.start()
    chunks.put(AudioChunk(path, "SYSTEM", 0, 1))
    chunks.put(None)
    chunks.join()
    worker.join()
    writer.close()
    assert not path.exists()
    assert "ok" in (tmp_path / "meeting/transcript.txt").read_text()


def test_worker_preserves_failed_chunk_and_continues(tmp_path: Path) -> None:
    path = tmp_path / "failed.wav"
    write_wav(path, np.ones(100, dtype=np.float32))
    chunks: queue.Queue[AudioChunk | None] = queue.Queue()
    writer = TranscriptWriter(tmp_path / "meeting")
    worker = TranscriptionWorker(
        chunks=chunks,
        transcriber=FailingTranscriber(),
        writer=writer,
        keep_audio=False,
        max_chunk_retries=1,
    )
    worker.start()
    chunks.put(AudioChunk(path, "MIC", 0, 1))
    chunks.put(None)
    chunks.join()
    worker.join()
    writer.close()
    assert path.exists()
    assert worker.failures == ["failed.wav"]
