import pytest

from meeting_assistant.llm.chunking import approximate_tokens, chunk_transcript


def test_long_transcript_chunks_by_estimated_tokens() -> None:
    text = "\n".join(f"[{index:03d}] " + "technical discussion " * 20 for index in range(100))
    chunks = chunk_transcript(text, 300)
    assert len(chunks) > 1
    assert all(chunk.strip() for chunk in chunks)
    assert approximate_tokens(text) > 300


def test_invalid_budget() -> None:
    with pytest.raises(ValueError):
        chunk_transcript("hello", 10)
