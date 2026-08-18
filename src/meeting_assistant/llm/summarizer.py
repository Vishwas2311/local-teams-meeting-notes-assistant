"""Hierarchical map/reduce summarization with schema validation."""

from __future__ import annotations

import json
from typing import Any, Protocol

from meeting_assistant.exceptions import AzureOpenAIError
from meeting_assistant.llm.chunking import approximate_tokens, chunk_transcript
from meeting_assistant.llm.prompts import FINAL_PROMPT, MAP_PROMPT
from meeting_assistant.models.schemas import MeetingInfo, MeetingNotes


class JSONGenerator(Protocol):
    def generate_json(self, prompt: str, max_output_tokens: int = 4000) -> dict[str, Any]: ...


class HierarchicalSummarizer:
    def __init__(self, client: JSONGenerator, token_budget: int = 6000) -> None:
        self.client = client
        self.token_budget = token_budget

    def summarize(self, transcript: str, info: MeetingInfo) -> MeetingNotes:
        if not transcript.strip():
            return MeetingNotes(meeting=info, summary="No speech was transcribed.")
        transcript_chunks = chunk_transcript(transcript, self.token_budget)
        evidence: list[dict[str, Any]] = []
        for chunk in transcript_chunks:
            evidence.append(self.client.generate_json(MAP_PROMPT + chunk))
        compact = json.dumps(evidence, ensure_ascii=False, separators=(",", ":"))
        # Reduce recursively if map outputs themselves exceed the context allowance.
        while approximate_tokens(compact) > self.token_budget * 2 and len(evidence) > 1:
            reduced: list[dict[str, Any]] = []
            for group in _groups(evidence, 4):
                reduced.append(
                    self.client.generate_json(
                        MAP_PROMPT + json.dumps(group, ensure_ascii=False, separators=(",", ":"))
                    )
                )
            evidence = reduced
            compact = json.dumps(evidence, ensure_ascii=False, separators=(",", ":"))
        metadata = json.dumps(info.model_dump(), ensure_ascii=False)
        final = self.client.generate_json(FINAL_PROMPT.format(metadata=metadata) + compact, 5000)
        try:
            notes = MeetingNotes.model_validate(final)
        except ValueError as exc:
            raise AzureOpenAIError(
                "Azure meeting-note JSON did not match the required schema"
            ) from exc
        notes.meeting = info  # Local metadata is authoritative.
        return notes


def _groups(values: list[dict[str, Any]], size: int) -> list[list[dict[str, Any]]]:
    return [values[index : index + size] for index in range(0, len(values), size)]
