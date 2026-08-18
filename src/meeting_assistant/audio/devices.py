"""Device discovery and portable non-secret preferences."""

from __future__ import annotations

import json
from pathlib import Path

from meeting_assistant.audio.base import AudioDevice, AudioSource
from meeting_assistant.audio.wasapi import PyAudioWPatchBackend
from meeting_assistant.exceptions import AudioCaptureError
from meeting_assistant.utils.files import atomic_write_json

PREFERENCES_PATH = Path(".local/config.json")


def list_devices() -> list[AudioDevice]:
    with PyAudioWPatchBackend() as backend:
        return backend.list_devices()


def load_preferences(path: Path = PREFERENCES_PATH) -> dict[str, str]:
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return {str(key): str(item) for key, item in value.items()}
    except (OSError, json.JSONDecodeError, TypeError) as exc:
        raise AudioCaptureError(f"Could not read device preferences at {path}: {exc}") from exc


def save_preferences(system: AudioDevice, microphone: AudioDevice | None) -> None:
    atomic_write_json(
        PREFERENCES_PATH,
        {
            "system_audio_device": system.stable_key,
            "system_audio_name": system.name,
            "microphone_device": microphone.stable_key if microphone else "",
            "microphone_name": microphone.name if microphone else "",
        },
    )


def devices_of_kind(devices: list[AudioDevice], kind: AudioSource) -> list[AudioDevice]:
    return [device for device in devices if device.kind == kind]
