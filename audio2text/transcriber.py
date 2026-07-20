from __future__ import annotations

import os
import threading
from collections.abc import Callable
from pathlib import Path

import av
import ctranslate2
from faster_whisper import WhisperModel

from .exporters import TranscriptSegment, TranscriptionResult

ProgressCallback = Callable[[float, str], None]
StatusCallback = Callable[[str], None]


class TranscriptionCancelled(RuntimeError):
    pass


class AudioTranscriber:
    """Carga un modelo Whisper y lo reutiliza para todos los archivos del lote."""

    VALID_PROFILES = {"auto", "fast", "balanced", "accurate"}

    def __init__(
        self,
        model_name: str,
        device: str = "auto",
        compute_type: str = "auto",
        performance_profile: str = "auto",
        model_cache_dir: str | Path | None = None,
        status_callback: StatusCallback | None = None,
    ) -> None:
        self.model_name = model_name
        self.device = self._resolve_device(device)
        self.compute_type = self._resolve_compute_type(compute_type, self.device)
        self.performance_profile = self._resolve_profile(performance_profile)
        self.cpu_threads = self._resolve_cpu_threads(self.device, self.performance_profile)
        self.model_cache_dir = Path(
            model_cache_dir or Path.home() / ".cache" / "audio2text" / "models"
        )
        self.model_cache_dir.mkdir(parents=True, exist_ok=True)
        self.status_callback = status_callback

        self._status(
            f"Cargando modelo {model_name} en {self.device} ({self.compute_type}). "
            "La primera vez puede descargar archivos desde Internet."
        )

        self.model = WhisperModel(
            model_name,
            device=self.device,
            compute_type=self.compute_type,
            cpu_threads=self.cpu_threads,
            num_workers=1,
            download_root=str(self.model_cache_dir),
        )

        thread_text = (
            f", {self.cpu_threads} hilo(s) de CPU" if self.device == "cpu" else ""
        )
        self._status(
            f"Modelo listo: {model_name}, {self.device}, {self.compute_type}{thread_text}."
        )

    def _status(self, text: str) -> None:
        if self.status_callback:
            self.status_callback(text)

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

    @classmethod
    def _resolve_profile(cls, profile: str) -> str:
        normalized = profile.strip().lower()
        return normalized if normalized in cls.VALID_PROFILES else "auto"

    @staticmethod
    def _resolve_cpu_threads(device: str, profile: str) -> int:
        if device != "cpu":
            return 0

        logical_cores = max(1, os.cpu_count() or 1)
        # Dejamos al menos un núcleo libre para que Windows y la interfaz respondan.
        available = max(1, logical_cores - 1)
        limits = {
            "fast": 4,
            "balanced": 6,
            "accurate": 8,
            "auto": 4 if logical_cores <= 8 else 6,
        }
        return max(1, min(available, limits[profile]))

    @staticmethod
    def _probe_duration(source: Path) -> float | None:
        """Obtiene una duración aproximada sin decodificar el archivo completo."""
        try:
            with av.open(str(source)) as container:
                if container.duration is not None:
                    return max(float(container.duration) / float(av.time_base), 0.0)

                audio_stream = next(
                    (stream for stream in container.streams if stream.type == "audio"),
                    None,
                )
                if (
                    audio_stream is not None
                    and audio_stream.duration is not None
                    and audio_stream.time_base is not None
                ):
                    return max(
                        float(audio_stream.duration * audio_stream.time_base),
                        0.0,
                    )
        except Exception:
            return None
        return None

    def _transcription_options(self, duration_hint: float | None) -> dict:
        short_audio = duration_hint is not None and duration_hint <= 15.0
        profile = self.performance_profile

        if profile == "accurate":
            beam_size = 5
            best_of = 5
            condition_on_previous_text = True
        elif profile == "balanced" or (profile == "auto" and self.device == "cuda"):
            beam_size = 3
            best_of = 3
            condition_on_previous_text = True
        else:
            # En CPU y en modo rápido, greedy decoding reduce mucho la latencia.
            beam_size = 1
            best_of = 1
            condition_on_previous_text = False

        # En clips muy cortos el VAD agrega trabajo y puede eliminar una frase breve.
        use_vad = not short_audio and profile != "fast"

        return {
            "beam_size": beam_size,
            "best_of": best_of,
            "condition_on_previous_text": condition_on_previous_text,
            "vad_filter": use_vad,
            "vad_parameters": {"min_silence_duration_ms": 500} if use_vad else None,
        }

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
        if source.stat().st_size == 0:
            raise ValueError("El archivo está vacío.")

        duration_hint = self._probe_duration(source)
        options = self._transcription_options(duration_hint)
        duration_text = (
            f"{duration_hint:.1f} s" if duration_hint is not None else "duración desconocida"
        )
        vad_text = "con filtro de silencios" if options["vad_filter"] else "sin filtro de silencios"
        self._status(
            f"Analizando {source.name} ({duration_text}, {vad_text}, "
            f"beam {options['beam_size']})."
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
                progress_callback(
                    max(0.02, min(float(segment.end) / duration, 0.98)),
                    text,
                )

        if progress_callback:
            progress_callback(1.0, "Transcripción terminada.")

        if not transcript_segments:
            self._status(
                f"{source.name}: el archivo se procesó correctamente, pero no se detectó voz."
            )

        return TranscriptionResult(
            source_file=str(source),
            language=info.language,
            language_probability=float(info.language_probability),
            duration=float(info.duration),
            segments=transcript_segments,
        )
