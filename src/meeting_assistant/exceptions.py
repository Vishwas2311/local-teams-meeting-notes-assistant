"""Application exception hierarchy."""


class MeetingAssistantError(Exception):
    """Base error presented safely by the CLI."""


class ConfigurationError(MeetingAssistantError):
    """Configuration is invalid or incomplete."""


class AudioCaptureError(MeetingAssistantError):
    """Audio capture failed."""


class AudioDeviceNotFoundError(AudioCaptureError):
    """A configured audio device cannot be resolved."""


class TranscriptionError(MeetingAssistantError):
    """Local transcription failed."""


class AzureOpenAIError(MeetingAssistantError):
    """Azure OpenAI request failed without exposing secrets."""


class StorageError(MeetingAssistantError):
    """Local persistence failed."""
