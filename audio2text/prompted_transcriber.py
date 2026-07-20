from __future__ import annotations

import threading
from pathlib import Path

from .exporters import TranscriptSegment, TranscriptionResult
from .transcriber import AudioTranscriber, ProgressCallback, TranscriptionCancelled


class PromptedAudioTranscriber(AudioTranscriber):
    """AudioTranscriber con vocabulario contextual opcional."""

    def transcribe_file(
        self,
        audio_path: str | Path,
        language: str | None = None,
        progress_callback: ProgressCallback | None = None,
        cancel_event: threading.Event | None = None,
        initial_prompt: str | None = None,
    ) -> TranscriptionResult:
        source = Path(audio_path)
        if not source.is_file():
            raise FileNotFoundError(f"No existe el archivo: {source}")
        if source.stat().st_size == 0:
            raise ValueError("El archivo está vacío.")

        duration_hint = self._probe_duration(source)
        options = self._transcription_options(duration_hint)
        duration_text = f"{duration_hint:.1f} s" if duration_hint is not None else "duración desconocida"
        vad_text = "con filtro de silencios" if options["vad_filter"] else "sin filtro de silencios"
        self._status(
            f"Analizando {source.name} ({duration_text}, {vad_text}, beam {options['beam_size']})."
        )
        if progress_callback:
            progress_callback(0.02, "Abriendo y preparando el audio…")

        segments, info = self.model.transcribe(
            str(source),
            language=language,
            task="transcribe",
            beam_size=options["beam_size"],
            best_of=options["best_of"],
            temperature=0.0,
            vad_filter=options["vad_filter"],
            vad_parameters=options["vad_parameters"],
            word_timestamps=False,
            condition_on_previous_text=options["condition_on_previous_text"],
            language_detection_segments=1,
            initial_prompt=initial_prompt or None,
        )

        duration = max(float(info.duration), duration_hint or 0.0, 0.001)
        transcript_segments: list[TranscriptSegment] = []
        for segment in segments:
            if cancel_event and cancel_event.is_set():
                raise TranscriptionCancelled("Transcripción cancelada por el usuario.")
            text = segment.text.strip()
            if text:
                transcript_segments.append(
                    TranscriptSegment(
                        start=float(segment.start),
                        end=float(segment.end),
                        text=text,
                    )
                )
            if progress_callback:
                progress_callback(max(0.02, min(float(segment.end) / duration, 0.98)), text)

        if progress_callback:
            progress_callback(1.0, "Transcripción terminada.")
        if not transcript_segments:
            self._status(f"{source.name}: el archivo se procesó, pero no se detectó voz.")

        return TranscriptionResult(
            source_file=str(source),
            language=info.language,
            language_probability=float(info.language_probability),
            duration=float(info.duration),
            segments=transcript_segments,
        )
