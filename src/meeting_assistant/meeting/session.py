"""End-to-end meeting lifecycle and graceful shutdown."""

from __future__ import annotations

import logging
import queue
import shutil
import threading
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from meeting_assistant.audio.base import AudioDevice
from meeting_assistant.audio.recorder import AudioChunk, CaptureProducer
from meeting_assistant.audio.wasapi import PyAudioWPatchBackend
from meeting_assistant.config import Settings
from meeting_assistant.llm.azure_openai import AzureResponsesClient
from meeting_assistant.llm.summarizer import HierarchicalSummarizer
from meeting_assistant.meeting.metadata import meeting_info
from meeting_assistant.meeting.storage import MeetingStorage
from meeting_assistant.models.schemas import MeetingMetadata
from meeting_assistant.transcription.transcript import TranscriptWriter
from meeting_assistant.transcription.whisper import WhisperTranscriber
from meeting_assistant.transcription.worker import TranscriptionWorker

LOGGER = logging.getLogger(__name__)


class MeetingSession:
    """Own capture threads, transcription worker, persistence, and final summarization."""

    def __init__(
        self,
        settings: Settings,
        *,
        title: str,
        system_device: AudioDevice,
        microphone_device: AudioDevice | None,
        on_transcript_line: Callable[[str], None] | None = None,
    ) -> None:
        self.settings = settings
        self.storage = MeetingStorage(settings.data_directory, title)
        self.metadata = MeetingMetadata(
            meeting_id=self.storage.root.name,
            title=title,
            started_at=datetime.now().astimezone(),
            system_device=system_device.name,
            microphone_device=microphone_device.name if microphone_device else None,
        )
        self.system_device = system_device
        self.microphone_device = microphone_device
        self.stop_event = threading.Event()
        self.chunks: queue.Queue[AudioChunk | None] = queue.Queue(settings.audio_queue_size)
        self.writer = TranscriptWriter(self.storage.root, on_transcript_line)
        self.transcriber = WhisperTranscriber(
            model_name=settings.whisper_model,
            device=settings.whisper_device,
            compute_type=settings.whisper_compute_type,
            cache_dir=settings.whisper_model_cache,
            language=settings.whisper_language,
            vad=settings.enable_vad,
        )
        self.worker = TranscriptionWorker(
            chunks=self.chunks,
            transcriber=self.transcriber,
            writer=self.writer,
            keep_audio=settings.keep_raw_audio,
        )
        self.producers = [
            CaptureProducer(
                backend=PyAudioWPatchBackend(),
                device=system_device,
                source="SYSTEM",
                chunks_dir=self.storage.chunks,
                output_queue=self.chunks,
                chunk_seconds=settings.audio_chunk_seconds,
                stop_event=self.stop_event,
            )
        ]
        if microphone_device:
            self.producers.append(
                CaptureProducer(
                    backend=PyAudioWPatchBackend(),
                    device=microphone_device,
                    source="MIC",
                    chunks_dir=self.storage.chunks,
                    output_queue=self.chunks,
                    chunk_seconds=settings.audio_chunk_seconds,
                    stop_event=self.stop_event,
                )
            )
        self._started = False

    def start(self) -> None:
        self.storage.write_metadata(self.metadata)
        self.worker.start()
        for producer in self.producers:
            producer.start()
        self._started = True

    def stop_and_finalize(self) -> tuple[Path, Path | None, Exception | None]:
        if not self._started:
            return self.storage.root / "transcript.txt", None, None
        self.stop_event.set()
        for producer in self.producers:
            producer.join(timeout=self.settings.audio_chunk_seconds + 15)
            if producer.is_alive():
                LOGGER.error("Capture thread did not stop cleanly: %s", producer.name)
            if producer.error:
                self.metadata.incomplete_chunks.append(f"{producer.source}: capture error")
        self.chunks.put(None)
        self.chunks.join()
        self.worker.join(timeout=30)
        self.metadata.incomplete_chunks.extend(self.worker.failures)
        self.writer.close()
        self.metadata.ended_at = datetime.now().astimezone()
        self.metadata.status = "completed" if not self.metadata.incomplete_chunks else "incomplete"
        self.storage.write_metadata(self.metadata)
        if not self.settings.keep_raw_audio and not any(self.storage.chunks.iterdir()):
            shutil.rmtree(self.storage.chunks, ignore_errors=True)

        transcript_path = self.storage.root / "transcript.txt"
        notes_path: Path | None = None
        summary_error: Exception | None = None
        if self.settings.azure_configured:
            try:
                transcript = transcript_path.read_text(encoding="utf-8")
                client = AzureResponsesClient(self.settings)
                notes = HierarchicalSummarizer(
                    client, self.settings.azure_summary_token_budget
                ).summarize(transcript, meeting_info(self.metadata))
                self.storage.write_notes(notes)
                notes_path = self.storage.root / "meeting_notes.md"
            except Exception as exc:
                LOGGER.error("AI summarization failed: %s", exc)
                summary_error = exc
        return transcript_path, notes_path, summary_error


def summarize_existing(settings: Settings, directory: Path, force: bool = False) -> Path:
    settings.ensure_azure()
    transcript_path = directory / "transcript.txt"
    metadata_path = directory / "metadata.json"
    notes_path = directory / "meeting_notes.md"
    if not transcript_path.is_file() or not metadata_path.is_file():
        raise FileNotFoundError("Meeting directory must contain transcript.txt and metadata.json")
    if notes_path.exists() and not force:
        raise FileExistsError("Meeting notes already exist; pass --force to regenerate")
    metadata = MeetingMetadata.model_validate_json(metadata_path.read_text(encoding="utf-8"))
    notes = HierarchicalSummarizer(
        AzureResponsesClient(settings), settings.azure_summary_token_budget
    ).summarize(transcript_path.read_text(encoding="utf-8"), meeting_info(metadata))
    storage = object.__new__(MeetingStorage)
    storage.root = directory
    storage.logs = directory / "logs"
    storage.chunks = directory / "audio"
    storage.write_notes(notes)
    return notes_path
