"""SoundCard-based WASAPI fallback for systems where PyAudioWPatch cannot open a device."""

from __future__ import annotations

import sys
from typing import Any

import numpy as np
from numpy.typing import NDArray

from meeting_assistant.audio.base import AudioCaptureBackend, AudioDevice, AudioSource
from meeting_assistant.exceptions import AudioCaptureError, AudioDeviceNotFoundError


class SoundCardBackend(AudioCaptureBackend):
    def __init__(self) -> None:
        if sys.platform != "win32":
            raise AudioCaptureError("SoundCard WASAPI capture is available only on Windows")
        try:
            import soundcard
        except ImportError as exc:
            raise AudioCaptureError("SoundCard fallback is not installed") from exc
        self._sc = soundcard
        self._recorder: Any | None = None
        self._sample_rate = 48000
        self._devices: dict[int, Any] = {}

    def list_devices(self) -> list[AudioDevice]:
        result: list[AudioDevice] = []
        self._devices.clear()
        for index, mic in enumerate(self._sc.all_microphones(include_loopback=True)):
            name = str(mic.name)
            loopback = "loopback" in name.casefold()
            kind: AudioSource = "SYSTEM" if loopback else "MIC"
            self._devices[index] = mic
            result.append(
                AudioDevice(
                    index=index,
                    name=name,
                    host_api="Windows WASAPI",
                    input_channels=max(1, len(getattr(mic, "channels", [0, 1]))),
                    output_channels=0,
                    sample_rate=48000,
                    kind=kind,
                    loopback=loopback,
                    backend="soundcard",
                )
            )
        return result

    def select_device(self, selector: str | None, kind: AudioSource) -> AudioDevice:
        candidates = [d for d in self.list_devices() if d.kind == kind]
        if selector:
            matches = [d for d in candidates if selector.casefold() in d.name.casefold()]
            if len(matches) == 1:
                return matches[0]
        if not candidates:
            raise AudioDeviceNotFoundError(f"No SoundCard {kind.lower()} device was found")
        return candidates[0]

    def start(self, device: AudioDevice) -> None:
        if not self._devices:
            self.list_devices()
        try:
            self._sample_rate = device.sample_rate
            self._recorder = self._devices[device.index].recorder(samplerate=self._sample_rate)
            self._recorder.__enter__()
        except Exception as exc:
            raise AudioCaptureError(f"SoundCard could not open '{device.name}': {exc}") from exc

    def read(self, frames: int) -> NDArray[np.float32]:
        if self._recorder is None:
            raise AudioCaptureError("SoundCard stream is not active")
        return np.asarray(self._recorder.record(numframes=frames), dtype=np.float32)

    def stop(self) -> None:
        if self._recorder is not None:
            self._recorder.__exit__(None, None, None)
            self._recorder = None
