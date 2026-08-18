from pathlib import Path

import pytest
from pydantic import ValidationError

from meeting_assistant.config import Settings
from meeting_assistant.exceptions import ConfigurationError


def test_defaults_are_cpu_safe(tmp_path: Path) -> None:
    settings = Settings(_env_file=None, data_directory=tmp_path)
    assert settings.whisper_device == "cpu"
    assert settings.whisper_compute_type == "int8"
    assert settings.audio_chunk_seconds == 20


def test_chunk_range_is_validated() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, audio_chunk_seconds=2)


def test_azure_base_url_and_required_fields() -> None:
    settings = Settings(
        _env_file=None,
        azure_openai_endpoint="https://example.openai.azure.com",
        azure_openai_api_key="secret",
        azure_openai_deployment="deployment",
    )
    assert settings.azure_base_url == "https://example.openai.azure.com/openai/v1/"
    settings.ensure_azure()
    with pytest.raises(ConfigurationError):
        Settings(_env_file=None).ensure_azure()


def test_rejects_non_https_azure_endpoint() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, azure_openai_endpoint="http://insecure.example")
