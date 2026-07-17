from __future__ import annotations

import threading
from collections.abc import Callable
from pathlib import Path

import ctranslate2
from faster_whisper import WhisperModel

from .exporters import TranscriptSegment, TranscriptionResult

ProgressCallback = Callable[[float, str], None]
StatusCallback = Callable[[str], None]


class TranscriptionCancelled(RuntimeError):
    pass


class AudioTranscriber:
    """Loads one Whisper model and reuses it for every file in a batch."""

    def __init__(
        self,
        model_name: str,
        device: str = "auto",
        compute_type: str = "auto",
        model_cache_dir: str | Path | None = None,
        status_callback: StatusCallback | None = None,
    ) -> None:
        self.model_name = model_name
        self.device = self._resolve_device(device)
        self.compute_type = self._resolve_compute_type(compute_type, self.device)
        self.model_cache_dir = Path(model_cache_dir or Path.home() / ".cache" / "audio2text" / "models")
        self.model_cache_dir.mkdir(parents=True, exist_ok=True)

        if status_callback:
            status_callback(
                f"Cargando modelo {model_name} en {self.device} ({self.compute_type}). "
                "La primera vez puede requerir una descarga."
            )

        self.model = WhisperModel(
            model_name,
            device=self.device,
            compute_type=self.compute_type,
            download_root=str(self.model_cache_dir),
        )

    @staticmethod
    def _resolve_device(device: str) -> str:
        if device != "auto":
            return device
        try:
            return "cuda" if ctranslate2.get_cuda_device_count() > 0 else "cpu"
        except Exception:
            return "cpu"

    @staticmethod
    def _resolve_compute_type(compute_type: str, device: str) -> str:
        if compute_type != "auto":
            return compute_type
        return "float16" if device == "cuda" else "int8"

    def transcribe_file(
        self,
        audio_path: str | Path,
        language: str | None = None,
        progress_callback: ProgressCallback | None = None,
        cancel_event: threading.Event | None = None,
    ) -> TranscriptionResult:
        source = Path(audio_path)
        if not source.is_file():
            raise FileNotFoundError(f"No existe el archivo: {source}")

        segments, info = self.model.transcribe(
            str(source),
            language=language,
            task="transcribe",
            beam_size=5,
            vad_filter=True,
            word_timestamps=False,
            condition_on_previous_text=True,
        )

        duration = max(float(info.duration), 0.001)
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
                progress_callback(
                    min(float(segment.end) / duration, 1.0),
                    text,
                )

        if progress_callback:
            progress_callback(1.0, "")

        return TranscriptionResult(
            source_file=str(source),
            language=info.language,
            language_probability=float(info.language_probability),
            duration=float(info.duration),
            segments=transcript_segments,
        )
