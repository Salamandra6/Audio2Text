from __future__ import annotations

import shutil
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Callable, Iterable

from .exporters import TranscriptSegment, TranscriptionResult

ProgressCallback = Callable[[str], None]


@dataclass(slots=True, frozen=True)
class SpeakerTurn:
    start: float
    end: float
    speaker: str


def module_status() -> tuple[bool, str]:
    try:
        import pyannote.audio  # noqa: F401
        import torch  # noqa: F401
    except Exception as exc:
        return False, f"Módulo no instalado: {type(exc).__name__}: {exc}"
    if shutil.which("ffmpeg") is None:
        return False, "FFmpeg no está disponible en PATH. Es necesario para el módulo de personas."
    return True, "Módulo de identificación de personas disponible."


def assign_person_labels(
    result: TranscriptionResult,
    turns: Iterable[SpeakerTurn],
) -> TranscriptionResult:
    ordered_turns = sorted(turns, key=lambda item: (item.start, item.end))
    speaker_numbers: dict[str, str] = {}
    for turn in ordered_turns:
        if turn.speaker not in speaker_numbers:
            speaker_numbers[turn.speaker] = f"Persona {len(speaker_numbers) + 1}"

    assigned: list[TranscriptSegment] = []
    for segment in result.segments:
        best_speaker: str | None = None
        best_overlap = 0.0
        segment_middle = (segment.start + segment.end) / 2.0
        nearest_distance = float("inf")
        nearest_speaker: str | None = None

        for turn in ordered_turns:
            overlap = max(0.0, min(segment.end, turn.end) - max(segment.start, turn.start))
            if overlap > best_overlap:
                best_overlap = overlap
                best_speaker = turn.speaker
            turn_middle = (turn.start + turn.end) / 2.0
            distance = abs(segment_middle - turn_middle)
            if distance < nearest_distance:
                nearest_distance = distance
                nearest_speaker = turn.speaker

        raw_speaker = best_speaker or nearest_speaker
        label = speaker_numbers.get(raw_speaker) if raw_speaker else None
        assigned.append(replace(segment, speaker=label))
    return replace(result, segments=assigned)


class SpeakerDiarizer:
    MODEL_ID = "pyannote/speaker-diarization-community-1"

    def __init__(self) -> None:
        self._cache_key: tuple[str, str] | None = None
        self._pipeline = None

    def process(
        self,
        result: TranscriptionResult,
        token: str,
        device: str = "auto",
        expected_people: int | None = None,
        status_callback: ProgressCallback | None = None,
    ) -> TranscriptionResult:
        available, detail = module_status()
        if not available:
            raise RuntimeError(detail)
        if not token.strip():
            raise ValueError("Ingresa un token de Hugging Face para identificar personas.")

        import torch
        from pyannote.audio import Pipeline

        resolved_device = "cuda" if device != "cpu" and torch.cuda.is_available() else "cpu"
        cache_key = (token.strip(), resolved_device)
        if self._pipeline is None or self._cache_key != cache_key:
            if status_callback:
                status_callback("Cargando el modelo de identificación de personas…")
            pipeline = Pipeline.from_pretrained(self.MODEL_ID, token=token.strip())
            if resolved_device == "cuda":
                pipeline.to(torch.device("cuda"))
            self._pipeline = pipeline
            self._cache_key = cache_key

        kwargs = {}
        if expected_people and expected_people > 0:
            kwargs["min_speakers"] = expected_people
            kwargs["max_speakers"] = expected_people
        if status_callback:
            status_callback("Analizando cambios de persona. Esta etapa puede tardar más que la transcripción…")
        output = self._pipeline(str(Path(result.source_file)), **kwargs)
        diarization = getattr(output, "exclusive_speaker_diarization", None)
        if diarization is None:
            diarization = output.speaker_diarization

        turns = [
            SpeakerTurn(float(turn.start), float(turn.end), str(speaker))
            for turn, speaker in diarization
        ]
        if not turns:
            raise RuntimeError("El módulo terminó, pero no identificó intervenciones de personas.")
        return assign_person_labels(result, turns)
