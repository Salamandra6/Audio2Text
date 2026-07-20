from __future__ import annotations

import re
from dataclasses import replace

from .exporters import TranscriptSegment, TranscriptionResult
from .research_analysis import timestamp

MARKER_RE = re.compile(r"^\[#(?P<index>\d+)\s+(?P<time>\d{2}:\d{2}:\d{2})\]\s*(?P<text>.*)$")


def editor_text(result: TranscriptionResult) -> str:
    lines = []
    for index, segment in enumerate(result.segments, start=1):
        lines.append(f"[#{index:04d} {timestamp(segment.start)}] {segment.text.strip()}")
    return "\n".join(lines)


def result_from_editor_text(result: TranscriptionResult, text: str) -> TranscriptionResult:
    original = result.segments
    if not original:
        content = text.strip()
        segments = [TranscriptSegment(0.0, max(result.duration, 0.001), content)] if content else []
        return replace(result, segments=segments)

    edited: dict[int, str] = {}
    last_index: int | None = None
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        match = MARKER_RE.match(line)
        if match:
            index = int(match.group("index")) - 1
            if 0 <= index < len(original):
                edited[index] = match.group("text").strip()
                last_index = index
            continue
        if line.strip() and last_index is not None:
            edited[last_index] = f"{edited.get(last_index, '')} {line.strip()}".strip()

    if not edited and text.strip():
        return replace(
            result,
            segments=[TranscriptSegment(0.0, max(result.duration, 0.001), text.strip())],
        )

    segments = []
    for index, segment in enumerate(original):
        content = edited.get(index, segment.text.strip()).strip()
        if content:
            segments.append(replace(segment, text=content))
    return replace(result, segments=segments)
