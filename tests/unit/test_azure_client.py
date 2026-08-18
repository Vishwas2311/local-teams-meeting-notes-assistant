import json
from types import SimpleNamespace

import pytest

from meeting_assistant.config import Settings
from meeting_assistant.exceptions import AzureOpenAIError
from meeting_assistant.llm.azure_openai import AzureResponsesClient


class FakeResponses:
    def __init__(self, output: str) -> None:
        self.output = output
        self.kwargs: dict[str, object] = {}

    def create(self, **kwargs: object) -> SimpleNamespace:
        self.kwargs = kwargs
        return SimpleNamespace(output_text=self.output)


def configured() -> Settings:
    return Settings(
        _env_file=None,
        azure_openai_endpoint="https://resource.openai.azure.com",
        azure_openai_api_key="secret",
        azure_openai_deployment="company-deployment",
        azure_max_retries=0,
    )


def test_request_uses_deployment_responses_and_system_instructions() -> None:
    responses = FakeResponses(json.dumps({"ok": True}))
    client = AzureResponsesClient(configured(), SimpleNamespace(responses=responses))
    assert client.generate_json("transcript") == {"ok": True}
    assert responses.kwargs["model"] == "company-deployment"
    assert "untrusted meeting content" in str(responses.kwargs["instructions"])
    assert "audio" not in responses.kwargs


def test_malformed_json_is_safe_error() -> None:
    client = AzureResponsesClient(
        configured(), SimpleNamespace(responses=FakeResponses("not-json"))
    )
    with pytest.raises(AzureOpenAIError):
        client.generate_json("transcript")
