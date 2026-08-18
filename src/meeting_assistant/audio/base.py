"""Backend-neutral audio contracts."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Literal

import numpy as np
from numpy.typing import NDArray

AudioSource = Literal["SYSTEM", "MIC"]


@dataclass(frozen=True, slots=True)
class AudioDevice:
    index: int
    name: str
    host_api: str
    input_channels: int
    output_channels: int
    sample_rate: int
    kind: AudioSource
    loopback: bool = False
    backend: str = "pyaudiowpatch"

    @property
    def stable_key(self) -> str:
        return f"{self.backend}|{self.host_api}|{self.kind}|{self.name}".casefold()


class AudioCaptureBackend(ABC):
    """Interface implemented by system-loopback and microphone backends."""

    @abstractmethod
    def list_devices(self) -> list[AudioDevice]: ...

    @abstractmethod
    def select_device(self, selector: str | None, kind: AudioSource) -> AudioDevice: ...

    @abstractmethod
    def start(self, device: AudioDevice) -> None: ...

    @abstractmethod
    def read(self, frames: int) -> NDArray[np.float32]: ...

    @abstractmethod
    def stop(self) -> None: ...

    def __enter__(self) -> AudioCaptureBackend:
        return self

    def __exit__(self, *_: object) -> None:
        self.stop()
