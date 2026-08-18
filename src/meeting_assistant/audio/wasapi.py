"""Primary Windows WASAPI loopback backend using PyAudioWPatch."""

from __future__ import annotations

import logging
import sys
from typing import Any

import numpy as np
from numpy.typing import NDArray

from meeting_assistant.audio.base import AudioCaptureBackend, AudioDevice, AudioSource
from meeting_assistant.exceptions import AudioCaptureError, AudioDeviceNotFoundError

LOGGER = logging.getLogger(__name__)


class PyAudioWPatchBackend(AudioCaptureBackend):
    """Capture explicit WASAPI loopback pseudo-inputs or microphones."""

    def __init__(self) -> None:
        if sys.platform != "win32":
            raise AudioCaptureError("WASAPI audio capture is available only on Windows")
        try:
            import pyaudiowpatch as pyaudio
        except ImportError as exc:
            raise AudioCaptureError("PyAudioWPatch is not installed") from exc
        self._module = pyaudio
        self._audio: Any = pyaudio.PyAudio()
        self._stream: Any | None = None
        self._device: AudioDevice | None = None

    def list_devices(self) -> list[AudioDevice]:
        devices: list[AudioDevice] = []
        loopback_indexes = {
            int(info["index"]) for info in self._audio.get_loopback_device_info_generator()
        }
        for index in range(self._audio.get_device_count()):
            info = self._audio.get_device_info_by_index(index)
            host_info = self._audio.get_host_api_info_by_index(int(info["hostApi"]))
            is_loopback = index in loopback_indexes or bool(info.get("isLoopbackDevice", False))
            input_channels = int(info.get("maxInputChannels", 0))
            output_channels = int(info.get("maxOutputChannels", 0))
            if is_loopback:
                kind: AudioSource = "SYSTEM"
            elif input_channels > 0:
                kind = "MIC"
            else:
                continue
            devices.append(
                AudioDevice(
                    index=index,
                    name=str(info["name"]),
                    host_api=str(host_info["name"]),
                    input_channels=input_channels,
                    output_channels=output_channels,
                    sample_rate=int(float(info["defaultSampleRate"])),
                    kind=kind,
                    loopback=is_loopback,
                )
            )
        return devices

    def select_device(self, selector: str | None, kind: AudioSource) -> AudioDevice:
        candidates = [device for device in self.list_devices() if device.kind == kind]
        if selector:
            normalized = selector.casefold()
            exact = [
                d
                for d in candidates
                if d.stable_key == normalized or d.name.casefold() == normalized
            ]
            partial = [d for d in candidates if normalized in d.name.casefold()]
            matches = exact or partial
            if len(matches) == 1:
                return matches[0]
            if len(matches) > 1:
                raise AudioDeviceNotFoundError(
                    f"Device selector '{selector}' is ambiguous; use the full device name"
                )
            raise AudioDeviceNotFoundError(
                f"Configured {kind.lower()} device is unavailable: {selector}"
            )
        if kind == "SYSTEM":
            try:
                default = self._audio.get_default_wasapi_loopback()
                index = int(default["index"])
                return next(device for device in candidates if device.index == index)
            except (OSError, StopIteration):
                pass
        else:
            try:
                index = int(self._audio.get_default_input_device_info()["index"])
                return next(device for device in candidates if device.index == index)
            except (OSError, StopIteration):
                pass
        if not candidates:
            raise AudioDeviceNotFoundError(f"No {kind.lower()} devices were found")
        return candidates[0]

    def start(self, device: AudioDevice) -> None:
        if self._stream is not None:
            raise AudioCaptureError("Audio stream is already active")
        channels = max(1, device.input_channels)
        try:
            self._stream = self._audio.open(
                format=self._module.paFloat32,
                channels=channels,
                rate=device.sample_rate,
                input=True,
                input_device_index=device.index,
                frames_per_buffer=4096,
            )
            self._device = device
        except Exception as exc:
            raise AudioCaptureError(f"Could not open audio device '{device.name}': {exc}") from exc

    def read(self, frames: int) -> NDArray[np.float32]:
        if self._stream is None or self._device is None:
            raise AudioCaptureError("Audio stream is not active")
        try:
            raw = self._stream.read(frames, exception_on_overflow=False)
            channels = max(1, self._device.input_channels)
            return np.frombuffer(raw, dtype=np.float32).reshape(-1, channels).copy()
        except Exception as exc:
            raise AudioCaptureError(f"Audio read failed: {exc}") from exc

    def stop(self) -> None:
        if self._stream is not None:
            try:
                self._stream.stop_stream()
                self._stream.close()
            except Exception:
                LOGGER.exception("Audio stream cleanup failed")
            self._stream = None
        if self._audio is not None:
            self._audio.terminate()
            self._audio = None
