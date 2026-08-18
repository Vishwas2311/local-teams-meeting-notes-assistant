from pathlib import Path

import numpy as np

from meeting_assistant.audio.mixer import normalize_for_whisper
from meeting_assistant.audio.recorder import verify_audio_signal, write_wav


def test_stereo_downmix_and_resample() -> None:
    stereo = np.column_stack(
        [np.sin(np.linspace(0, 20, 48000)), np.sin(np.linspace(0, 20, 48000))]
    ).astype(np.float32)
    result = normalize_for_whisper(stereo, 48000)
    assert result.ndim == 1
    assert 15990 <= len(result) <= 16010
    assert np.max(np.abs(result)) <= 1


def test_wav_signal_verification(tmp_path: Path) -> None:
    path = tmp_path / "signal.wav"
    write_wav(path, np.sin(np.linspace(0, 100, 16000)).astype(np.float32))
    verify_audio_signal(path)
