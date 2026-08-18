"""Persistent faster-whisper model adapter."""

from __future__ import annotations

from pathlib import Path

from meeting_assistant.exceptions import TranscriptionError
from meeting_assistant.models.schemas import TranscriptSegment


class WhisperTranscriber:
    """Load one model once and transcribe local files only."""

    def __init__(
        self,
        *,
        model_name: str,
        device: str,
        compute_type: str,
        cache_dir: Path,
        language: str,
        vad: bool,
    ) -> None:
        try:
            from faster_whisper import WhisperModel

            cache_dir.mkdir(parents=True, exist_ok=True)
            self._model = WhisperModel(
                model_name,
                device=device,
                compute_type=compute_type,
                download_root=str(cache_dir),
            )
        except Exception as exc:
            raise TranscriptionError(f"Could not load Whisper model '{model_name}': {exc}") from exc
        self.language = None if language.casefold() == "auto" else language
        self.vad = vad

    def transcribe(self, path: Path, source: str, offset: float) -> list[TranscriptSegment]:
        try:
            segments, info = self._model.transcribe(
                str(path),
                language=self.language,
                vad_filter=self.vad,
                beam_size=5,
                condition_on_previous_text=False,
            )
            # Iteration triggers faster-whisper inference.
            return [
                TranscriptSegment(
                    start_seconds=offset + float(segment.start),
                    end_seconds=offset + float(segment.end),
                    text=str(segment.text).strip(),
                    source=source,
                    language=str(info.language) if info.language else None,
                )
                for segment in segments
                if str(segment.text).strip()
            ]
        except Exception as exc:
            raise TranscriptionError(f"Transcription failed for {path.name}: {exc}") from exc
