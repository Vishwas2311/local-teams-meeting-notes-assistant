"""Per-meeting local storage."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from meeting_assistant.models.schemas import MeetingMetadata, MeetingNotes
from meeting_assistant.utils.files import atomic_write_json, atomic_write_text, ensure_writable


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    return slug[:60] or "meeting"


class MeetingStorage:
    def __init__(self, data_directory: Path, title: str, now: datetime | None = None) -> None:
        started = now or datetime.now().astimezone()
        meeting_id = f"{started:%Y-%m-%d_%H%M%S}_{slugify(title)}"
        self.root = data_directory / "meetings" / meeting_id
        self.logs = self.root / "logs"
        self.chunks = self.root / "audio"
        ensure_writable(self.root)
        self.logs.mkdir(exist_ok=True)
        self.chunks.mkdir(exist_ok=True)

    def write_metadata(self, metadata: MeetingMetadata) -> None:
        atomic_write_json(self.root / "metadata.json", metadata.model_dump(mode="json"))

    def write_notes(self, notes: MeetingNotes) -> None:
        atomic_write_json(self.root / "meeting_notes.json", notes.model_dump(mode="json"))
        atomic_write_text(self.root / "meeting_notes.md", render_markdown(notes))


def render_markdown(notes: MeetingNotes) -> str:
    info = notes.meeting

    def bullets(values: list[str]) -> str:
        return "\n".join(f"- {value}" for value in values) if values else "- Not specified"

    actions = ["| Action | Owner | Deadline | Status |", "|---|---|---|---|"]
    for item in notes.action_items:
        safe = [
            value.replace("|", "\\|").replace("\n", " ")
            for value in (item.action, item.owner, item.deadline, item.status)
        ]
        actions.append("| " + " | ".join(safe) + " |")
    if not notes.action_items:
        actions.append("| Not specified | Not specified | Not specified | Open |")
    return f"""# Meeting Notes

## Meeting Information

Date: {info.date}  
Start Time: {info.start_time}  
End Time: {info.end_time}  
Duration: {info.duration}

## Executive Summary

{notes.summary or 'Not specified'}

## Key Discussion Points

{bullets(notes.discussion_points)}

## Decisions Made

{bullets(notes.decisions)}

## Action Items

{chr(10).join(actions)}

## Risks / Blockers

{bullets(notes.risks)}

## Open Questions

{bullets(notes.open_questions)}

## Follow-Up Items

{bullets(notes.follow_ups)}

## Important Technical Details

{bullets(notes.technical_details)}

## Topics Requiring Clarification

{bullets(notes.clarification_topics)}
"""
