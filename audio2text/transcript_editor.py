from __future__ import annotations

import re
from dataclasses import replace

from .exporters import TranscriptSegment, TranscriptionResult
from .research_analysis import timestamp

MARKER_RE = re.compile(
    r"^\[#(?P<index>\d+)\s+(?P<time>\d{2}:\d{2}:\d{2})\]"
    r"(?:\s+\[(?P<speaker>Persona\s+\d+)\])?\s*(?P<text>.*)$"
)


def timestamp_seconds(value: str) -> float:
    hours, minutes, seconds = (int(part) for part in value.split(":"))
    return float(hours * 3600 + minutes * 60 + seconds)


def marker_start_seconds(line: str) -> float | None:
    match = MARKER_RE.match(line.rstrip())
    return timestamp_seconds(match.group("time")) if match else None


def editor_text(result: TranscriptionResult) -> str:
    lines = []
    for index, segment in enumerate(result.segments, start=1):
        speaker = f" [{segment.speaker}]" if segment.speaker else ""
        lines.append(
            f"[#{index:04d} {timestamp(segment.start)}]{speaker} {segment.text.strip()}"
        )
    return "\n".join(lines)


def result_from_editor_text(result: TranscriptionResult, text: str) -> TranscriptionResult:
    original = result.segments
    if not original:
        content = text.strip()
        segments = [TranscriptSegment(0.0, max(result.duration, 0.001), content)] if content else []
        return replace(result, segments=segments)

    edited: dict[int, tuple[str, str | None]] = {}
    last_index: int | None = None
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        match = MARKER_RE.match(line)
        if match:
            index = int(match.group("index")) - 1
            if 0 <= index < len(original):
                speaker = match.group("speaker") or original[index].speaker
                edited[index] = (match.group("text").strip(), speaker)
                last_index = index
            continue
        if line.strip() and last_index is not None:
            previous, speaker = edited.get(last_index, ("", original[last_index].speaker))
            edited[last_index] = (f"{previous} {line.strip()}".strip(), speaker)

    if not edited and text.strip():
        return replace(
            result,
            segments=[TranscriptSegment(0.0, max(result.duration, 0.001), text.strip())],
        )

    segments = []
    for index, segment in enumerate(original):
        content, speaker = edited.get(index, (segment.text.strip(), segment.speaker))
        content = content.strip()
        if content:
            segments.append(replace(segment, text=content, speaker=speaker))
    return replace(result, segments=segments)
