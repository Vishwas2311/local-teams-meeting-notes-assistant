"""Metadata helpers."""

from datetime import datetime

from meeting_assistant.models.schemas import MeetingInfo, MeetingMetadata
from meeting_assistant.utils.time import format_duration


def meeting_info(metadata: MeetingMetadata) -> MeetingInfo:
    ended = metadata.ended_at or datetime.now().astimezone()
    duration = (ended - metadata.started_at).total_seconds()
    return MeetingInfo(
        date=metadata.started_at.date().isoformat(),
        start_time=metadata.started_at.strftime("%H:%M:%S %Z"),
        end_time=ended.strftime("%H:%M:%S %Z"),
        duration=format_duration(duration),
    )
