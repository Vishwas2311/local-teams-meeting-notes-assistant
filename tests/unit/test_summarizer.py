from typing import Any

import pytest

from meeting_assistant.exceptions import AzureOpenAIError
from meeting_assistant.llm.summarizer import HierarchicalSummarizer
from meeting_assistant.models.schemas import MeetingInfo


class FakeLLM:
    def __init__(self, malformed: bool = False) -> None:
        self.calls = 0
        self.malformed = malformed

    def generate_json(self, prompt: str, max_output_tokens: int = 4000) -> dict[str, Any]:
        self.calls += 1
        if "Synthesize final" not in prompt:
            return {"discussion_points": ["API discussed"]}
        if self.malformed:
            return {"action_items": "wrong"}
        return {
            "meeting": {},
            "summary": "API discussion",
            "discussion_points": ["API discussed"],
            "decisions": [],
            "action_items": [
                {
                    "action": "Investigate Redis",
                    "owner": "Not specified",
                    "deadline": "Not specified",
                }
            ],
        }


def test_empty_transcript_does_not_call_azure() -> None:
    llm = FakeLLM()
    notes = HierarchicalSummarizer(llm).summarize("", MeetingInfo())
    assert llm.calls == 0
    assert "No speech" in notes.summary


def test_map_reduce_validates_and_preserves_local_metadata() -> None:
    llm = FakeLLM()
    info = MeetingInfo(date="2026-08-18", start_time="10:00", end_time="11:00", duration="1:00:00")
    notes = HierarchicalSummarizer(llm, token_budget=1000).summarize("[00:00] Discuss API", info)
    assert notes.meeting == info
    assert notes.action_items[0].owner == "Not specified"
    assert llm.calls == 2


def test_malformed_model_schema_is_rejected() -> None:
    with pytest.raises(AzureOpenAIError):
        HierarchicalSummarizer(FakeLLM(malformed=True), 1000).summarize("speech", MeetingInfo())
