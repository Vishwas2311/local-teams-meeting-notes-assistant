from datetime import datetime
from pathlib import Path

from meeting_assistant.meeting.storage import MeetingStorage, render_markdown, slugify
from meeting_assistant.models.schemas import ActionItem, MeetingNotes


def test_slug_and_storage_are_deterministic(tmp_path: Path) -> None:
    assert slugify("Document Extraction / API") == "document-extraction-api"
    storage = MeetingStorage(tmp_path, "Test Meeting", datetime(2026, 8, 18, 10, 30))
    assert storage.root.name == "2026-08-18_103000_test-meeting"


def test_markdown_action_table_escapes_pipe() -> None:
    markdown = render_markdown(
        MeetingNotes(
            action_items=[ActionItem(action="Build A | B", owner="Rajshree", deadline="Friday")]
        )
    )
    assert "Rajshree" in markdown
    assert "Build A \\| B" in markdown
