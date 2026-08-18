"""Approximate-token transcript chunking."""

from __future__ import annotations


def approximate_tokens(text: str) -> int:
    """Conservative multilingual approximation without adding a tokenizer dependency."""
    if not text:
        return 0
    words = len(text.split())
    chars = len(text)
    return max(words * 2, (chars + 2) // 3)


def chunk_transcript(text: str, token_budget: int) -> list[str]:
    if token_budget < 100:
        raise ValueError("token_budget must be at least 100")
    chunks: list[str] = []
    current: list[str] = []
    current_tokens = 0
    for line in text.splitlines():
        line_tokens = approximate_tokens(line + "\n")
        if line_tokens > token_budget:
            if current:
                chunks.append("\n".join(current))
                current, current_tokens = [], 0
            width = max(100, token_budget * 3)
            chunks.extend(line[start : start + width] for start in range(0, len(line), width))
        elif current and current_tokens + line_tokens > token_budget:
            chunks.append("\n".join(current))
            current, current_tokens = [line], line_tokens
        else:
            current.append(line)
            current_tokens += line_tokens
    if current:
        chunks.append("\n".join(current))
    return [chunk for chunk in chunks if chunk.strip()]
