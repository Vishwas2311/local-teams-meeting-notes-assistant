"""Non-blocking capture producers with bounded transcription queues."""

from __future__ import annotations

import logging
import queue
import threading
import wave
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from meeting_assistant.audio.base import AudioCaptureBackend, AudioDevice, AudioSource
from meeting_assistant.audio.mixer import TARGET_RATE, normalize_for_whisper, pcm16_bytes
from meeting_assistant.exceptions import AudioCaptureError

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class AudioChunk:
    path: Path
    source: AudioSource
    offset_seconds: float
    duration_seconds: float


def write_wav(path: Path, samples: np.ndarray, sample_rate: int = TARGET_RATE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(sample_rate)
        output.writeframes(pcm16_bytes(samples.astype(np.float32)))


class CaptureProducer(threading.Thread):
    """Read one source continuously and enqueue complete, persisted WAV chunks."""

    def __init__(
        self,
        *,
        backend: AudioCaptureBackend,
        device: AudioDevice,
        source: AudioSource,
        chunks_dir: Path,
        output_queue: queue.Queue[AudioChunk | None],
        chunk_seconds: int,
        stop_event: threading.Event,
    ) -> None:
        super().__init__(name=f"capture-{source.lower()}", daemon=True)
        self.backend = backend
        self.device = device
        self.source = source
        self.chunks_dir = chunks_dir
        self.output_queue = output_queue
        self.chunk_seconds = chunk_seconds
        self.stop_event = stop_event
        self.error: Exception | None = None
        self._sequence = 0

    def run(self) -> None:
        frames_per_read = min(4096, self.device.sample_rate)
        target_frames = self.device.sample_rate * self.chunk_seconds
        buffered: list[np.ndarray] = []
        buffered_frames = 0
        captured_frames = 0
        try:
            self.backend.start(self.device)
            while not self.stop_event.is_set():
                block = self.backend.read(frames_per_read)
                buffered.append(block)
                buffered_frames += len(block)
                if buffered_frames >= target_frames:
                    combined = np.concatenate(buffered, axis=0)
                    take, remainder = combined[:target_frames], combined[target_frames:]
                    self._persist_and_enqueue(take, captured_frames / self.device.sample_rate)
                    captured_frames += len(take)
                    buffered = [remainder] if len(remainder) else []
                    buffered_frames = len(remainder)
            if buffered_frames:
                combined = np.concatenate(buffered, axis=0)
                self._persist_and_enqueue(combined, captured_frames / self.device.sample_rate)
        except Exception as exc:
            self.error = exc
            LOGGER.exception("%s capture stopped unexpectedly", self.source)
        finally:
            self.backend.stop()

    def _persist_and_enqueue(self, samples: np.ndarray, offset: float) -> None:
        normalized = normalize_for_whisper(samples.astype(np.float32), self.device.sample_rate)
        if normalized.size == 0:
            return
        path = self.chunks_dir / f"{self.source.lower()}_{self._sequence:06d}.wav"
        write_wav(path, normalized)
        chunk = AudioChunk(path, self.source, offset, len(normalized) / TARGET_RATE)
        self._sequence += 1
        while True:
            try:
                self.output_queue.put(chunk, timeout=1)
                return
            except queue.Full:
                LOGGER.warning(
                    "Transcription queue full (%d); chunk remains safely on disk: %s",
                    self.output_queue.qsize(),
                    path.name,
                )


def verify_audio_signal(path: Path, minimum_rms: float = 0.0001) -> None:
    with wave.open(str(path), "rb") as source:
        raw = source.readframes(source.getnframes())
    samples = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32767
    rms = float(np.sqrt(np.mean(np.square(samples)))) if samples.size else 0.0
    if rms < minimum_rms:
        raise AudioCaptureError(
            "Capture completed but contains silence. Confirm that audio is playing through the "
            "selected device."
        )
