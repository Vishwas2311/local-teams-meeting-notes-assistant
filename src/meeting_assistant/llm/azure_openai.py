"""Official OpenAI Python SDK adapter for Azure OpenAI v1 Responses API."""

from __future__ import annotations

import json
import logging
from typing import Any

import openai
from openai import OpenAI

from meeting_assistant.config import Settings
from meeting_assistant.exceptions import AzureOpenAIError
from meeting_assistant.llm.prompts import SYSTEM_PROMPT
from meeting_assistant.utils.retry import with_retry

LOGGER = logging.getLogger(__name__)


class AzureResponsesClient:
    """Text-only Azure client; this class has no audio API surface."""

    def __init__(self, settings: Settings, client: Any | None = None) -> None:
        settings.ensure_azure()
        self.deployment = settings.azure_openai_deployment
        self.max_retries = settings.azure_max_retries
        self._client = client or OpenAI(
            api_key=settings.azure_openai_api_key,
            base_url=settings.azure_base_url,
            timeout=settings.azure_timeout_seconds,
            max_retries=0,  # Retry policy is centralized and testable here.
        )

    def health_check(self) -> None:
        self._request('Return only this JSON: {"ok":true}', max_output_tokens=30)

    def generate_json(self, prompt: str, max_output_tokens: int = 4000) -> dict[str, Any]:
        text = self._request(prompt, max_output_tokens=max_output_tokens)
        try:
            value = json.loads(_strip_json_fence(text))
        except json.JSONDecodeError as exc:
            raise AzureOpenAIError("Azure returned malformed JSON meeting notes") from exc
        if not isinstance(value, dict):
            raise AzureOpenAIError("Azure returned JSON that is not an object")
        return value

    def _request(self, prompt: str, max_output_tokens: int) -> str:
        def operation() -> str:
            response = self._client.responses.create(
                model=self.deployment,
                instructions=SYSTEM_PROMPT,
                input=prompt,
                max_output_tokens=max_output_tokens,
            )
            output = str(response.output_text).strip()
            if not output:
                raise AzureOpenAIError("Azure returned an empty response")
            return output

        try:
            return with_retry(
                operation,
                attempts=self.max_retries,
                retryable=_is_retryable,
            )
        except AzureOpenAIError:
            raise
        except openai.AuthenticationError as exc:
            raise AzureOpenAIError("Azure authentication failed (401). Check the API key.") from exc
        except openai.PermissionDeniedError as exc:
            raise AzureOpenAIError(
                "Azure access was denied (403). Check deployment permissions."
            ) from exc
        except openai.NotFoundError as exc:
            raise AzureOpenAIError(
                "Azure resource or deployment was not found (404). Check endpoint and "
                "deployment name."
            ) from exc
        except openai.RateLimitError as exc:
            raise AzureOpenAIError(
                "Azure rate limit persisted after bounded retries (429)."
            ) from exc
        except openai.APITimeoutError as exc:
            raise AzureOpenAIError("Azure request timed out after bounded retries.") from exc
        except openai.APIConnectionError as exc:
            raise AzureOpenAIError(
                "Could not connect to Azure. Check DNS, network, proxy, and endpoint."
            ) from exc
        except openai.BadRequestError as exc:
            raise AzureOpenAIError(
                "Azure rejected the request. The deployment may not support the Responses API."
            ) from exc
        except openai.APIError as exc:
            raise AzureOpenAIError("Azure API request failed.") from exc
        except Exception as exc:
            raise AzureOpenAIError(
                f"Unexpected Azure request failure: {type(exc).__name__}"
            ) from exc


def _is_retryable(exc: Exception) -> bool:
    return isinstance(
        exc,
        (
            openai.RateLimitError,
            openai.APITimeoutError,
            openai.APIConnectionError,
            openai.InternalServerError,
        ),
    )


def _strip_json_fence(text: str) -> str:
    value = text.strip()
    if value.startswith("```"):
        lines = value.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        value = "\n".join(lines)
    return value.strip()
