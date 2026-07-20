from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


@dataclass(slots=True)
class TranscriptSegment:
    start: float
    end: float
    text: str
    speaker: str | None = None


@dataclass(slots=True)
class TranscriptionResult:
    source_file: str
    language: str
    language_probability: float
    duration: float
    segments: list[TranscriptSegment]

    @property
    def text(self) -> str:
        return "\n".join(segment.text.strip() for segment in self.segments if segment.text.strip())


def _timestamp(seconds: float, decimal_marker: str = ",") -> str:
    milliseconds = max(0, round(seconds * 1000))
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}{decimal_marker}{millis:03d}"


def _segment_text(segment: TranscriptSegment) -> str:
    text = segment.text.strip()
    return f"{segment.speaker}: {text}" if segment.speaker else text


def to_srt(segments: Iterable[TranscriptSegment]) -> str:
    blocks: list[str] = []
    for index, segment in enumerate(segments, start=1):
        text = _segment_text(segment)
        if not text:
            continue
        blocks.append(
            f"{index}\n"
            f"{_timestamp(segment.start)} --> {_timestamp(segment.end)}\n"
            f"{text}"
        )
    return "\n\n".join(blocks) + ("\n" if blocks else "")


def to_vtt(segments: Iterable[TranscriptSegment]) -> str:
    blocks = ["WEBVTT"]
    for segment in segments:
        text = _segment_text(segment)
        if not text:
            continue
        blocks.append(
            f"{_timestamp(segment.start, '.')} --> {_timestamp(segment.end, '.')}\n{text}"
        )
    return "\n\n".join(blocks) + "\n"


def _unique_path(folder: Path, stem: str, suffix: str) -> Path:
    candidate = folder / f"{stem}{suffix}"
    counter = 2
    while candidate.exists():
        candidate = folder / f"{stem} ({counter}){suffix}"
        counter += 1
    return candidate


def export_result(
    result: TranscriptionResult,
    output_dir: str | Path,
    formats: Iterable[str],
) -> list[Path]:
    folder = Path(output_dir)
    folder.mkdir(parents=True, exist_ok=True)
    stem = Path(result.source_file).stem
    written: list[Path] = []

    for selected_format in formats:
        file_format = selected_format.lower().strip()
        if file_format == "txt":
            path = _unique_path(folder, stem, ".txt")
            lines = [_segment_text(segment) for segment in result.segments if segment.text.strip()]
            path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
        elif file_format == "srt":
            path = _unique_path(folder, stem, ".srt")
            path.write_text(to_srt(result.segments), encoding="utf-8")
        elif file_format == "vtt":
            path = _unique_path(folder, stem, ".vtt")
            path.write_text(to_vtt(result.segments), encoding="utf-8")
        elif file_format == "json":
            path = _unique_path(folder, stem, ".json")
            path.write_text(
                json.dumps(asdict(result), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        else:
            raise ValueError(f"Formato de salida no admitido: {selected_format}")
        written.append(path)

    return written
