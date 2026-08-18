import json
from pathlib import Path

from meeting_assistant.models.schemas import TranscriptSegment
from meeting_assistant.transcription.transcript import TranscriptWriter, load_segments


def test_transcript_is_incremental_and_source_tagged(tmp_path: Path) -> None:
    writer = TranscriptWriter(tmp_path)
    writer.append(
        TranscriptSegment(
            start_seconds=4.2, end_seconds=5.0, text="Hello", source="SYSTEM", language="en"
        )
    )
    assert "[00:00:04] [SYSTEM] Hello" in (tmp_path / "transcript.txt").read_text()
    payload = json.loads((tmp_path / "transcript.jsonl").read_text())
    assert payload["source"] == "SYSTEM"
    writer.close()
    assert load_segments(tmp_path / "transcript.jsonl")[0].text == "Hello"
