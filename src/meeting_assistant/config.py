"""Typed configuration loaded from environment variables and .env."""

from __future__ import annotations

from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings. Secret fields are never included in logs."""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", case_sensitive=False
    )

    app_env: str = "development"
    azure_openai_endpoint: str = ""
    azure_openai_api_key: str = Field(default="", repr=False)
    azure_openai_deployment: str = ""
    azure_timeout_seconds: float = Field(default=60, ge=5, le=300)
    azure_max_retries: int = Field(default=4, ge=0, le=10)
    azure_summary_token_budget: int = Field(default=6000, ge=1000, le=50000)

    whisper_model: str = "small"
    whisper_device: Literal["cpu", "cuda", "auto"] = "cpu"
    whisper_compute_type: str = "int8"
    whisper_language: str = "auto"
    whisper_model_cache: Path = Path("models")

    system_audio_device: str = ""
    microphone_device: str = ""
    capture_microphone: bool = True
    audio_chunk_seconds: int = Field(default=20, ge=10, le=60)
    audio_queue_size: int = Field(default=12, ge=2, le=100)
    capture_sample_rate: int = Field(default=48000, ge=16000, le=192000)
    enable_vad: bool = True
    keep_raw_audio: bool = False

    enable_periodic_summary: bool = False
    summary_interval_minutes: int = Field(default=15, ge=5, le=120)
    data_directory: Path = Path("data")
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    @field_validator("azure_openai_endpoint")
    @classmethod
    def validate_endpoint(cls, value: str) -> str:
        value = value.strip().rstrip("/")
        if not value:
            return value
        parsed = urlparse(value)
        if parsed.scheme != "https" or not parsed.netloc:
            raise ValueError("AZURE_OPENAI_ENDPOINT must be a valid HTTPS URL")
        return value

    @property
    def azure_configured(self) -> bool:
        return bool(
            self.azure_openai_endpoint
            and self.azure_openai_api_key
            and self.azure_openai_deployment
        )

    @property
    def azure_base_url(self) -> str:
        endpoint = self.azure_openai_endpoint
        if endpoint.endswith("/openai/v1"):
            return f"{endpoint}/"
        return f"{endpoint}/openai/v1/"

    def ensure_azure(self) -> None:
        missing = [
            name
            for name, value in (
                ("AZURE_OPENAI_ENDPOINT", self.azure_openai_endpoint),
                ("AZURE_OPENAI_API_KEY", self.azure_openai_api_key),
                ("AZURE_OPENAI_DEPLOYMENT", self.azure_openai_deployment),
            )
            if not value
        ]
        if missing:
            from meeting_assistant.exceptions import ConfigurationError

            raise ConfigurationError("Missing Azure configuration: " + ", ".join(missing))
