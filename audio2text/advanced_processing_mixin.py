from __future__ import annotations

import gc
import traceback

from .prompted_transcriber import PromptedAudioTranscriber
from .research_documents import export_research_result
from .speaker_diarization import SpeakerDiarizer
from .transcriber import TranscriptionCancelled

CUDA_RUNTIME_MARKERS = (
    "cuda",
    "cublas",
    "cudnn",
    "cufft",
    "cusolver",
    "cusparse",
    "nvrtc",
    "nvcuda",
    "libcublas",
    "library cublas64",
    "library cudnn",
    "driver version is insufficient",
    "no cuda-capable device",
)


def is_cuda_runtime_error(exc: BaseException) -> bool:
    text = f"{type(exc).__name__}: {exc}".lower()
    return any(marker in text for marker in CUDA_RUNTIME_MARKERS)


class AdvancedProcessingMixin:
    def __init__(self) -> None:
        self._speaker_diarizer = SpeakerDiarizer()
        super().__init__()

    def _create_transcriber(self, options: dict, phase: str) -> PromptedAudioTranscriber:
        self.events.put(("phase", phase, None))
        transcriber = PromptedAudioTranscriber(
            options["model"], options["device"], options["compute"],
            performance_profile=options["profile"],
            status_callback=lambda text: self.events.put(("phase", f"Etapa 2/6 · {text}", None)),
        )
        key = (options["model"], options["device"], options["compute"], options["profile"])
        self._transcriber_cache = (key, transcriber)
        return transcriber

    def _activate_cpu_fallback(self, options: dict, cause: BaseException) -> PromptedAudioTranscriber:
        original_device = options.get("device", "auto")
        original_compute = options.get("compute", "auto")
        options["device"] = "cpu"
        options["compute"] = "int8"
        options["profile"] = "fast"
        options["profile_label"] = "Rápido · respaldo automático CPU"
        self._transcriber_cache = None
        gc.collect()

        detail = (
            f"La GPU no pudo utilizarse ({type(cause).__name__}: {cause}). "
            f"Se cambió automáticamente de {original_device}/{original_compute} a CPU/int8."
        )
        self.events.put(("phase", "CUDA no disponible. Reintentando automáticamente con CPU/int8…", None))
        if hasattr(self, "_productivity_events"):
            self._productivity_events.put(("cuda_fallback", detail))
        return self._create_transcriber(
            options,
            "Etapa 2/6 · Cargando modelo de respaldo en CPU/int8…",
        )

    def _load_transcriber(self, options: dict) -> PromptedAudioTranscriber:
        key = (options["model"], options["device"], options["compute"], options["profile"])
        if self._transcriber_cache and self._transcriber_cache[0] == key:
            self.events.put(("phase", "Etapa 2/6 · Modelo reutilizado. Preparando audio…", None))
            return self._transcriber_cache[1]

        if self._transcriber_cache:
            self._transcriber_cache = None
            gc.collect()
        return self._create_transcriber(
            options,
            "Etapa 2/6 · Cargando el modelo de transcripción…",
        )

    def _safe_run_batch(self, options: dict) -> None:
        try:
            transcriber = self._load_transcriber(options)
        except Exception as exc:
            if options.get("device") != "cpu" and is_cuda_runtime_error(exc):
                try:
                    transcriber = self._activate_cpu_fallback(options, exc)
                except Exception as fallback_exc:
                    trace = (
                        "Fallo inicial al usar GPU:\n"
                        f"{traceback.format_exc()}\n\n"
                        "También falló el respaldo CPU/int8:\n"
                        f"{type(fallback_exc).__name__}: {fallback_exc}"
                    )
                    report = self._create_error_report(None, fallback_exc, options, trace)
                    self._terminal_event_queued = True
                    self.events.put(("error_detail", report))
                    self.events.put(("fatal", f"No se pudo cargar el modelo: {type(fallback_exc).__name__}: {fallback_exc}"))
                    return
            else:
                report = self._create_error_report(None, exc, options, traceback.format_exc())
                self._terminal_event_queued = True
                self.events.put(("error_detail", report))
                self.events.put(("fatal", f"No se pudo cargar el modelo: {type(exc).__name__}: {exc}"))
                return

        success = errors = 0
        total = len(options["files"])
        for index, path in enumerate(options["files"]):
            if self.cancel_event.is_set():
                break
            self.events.put(("file", index, "Procesando"))
            self.events.put(("phase", f"Etapa 3/6 · Transcribiendo {path.name} ({index + 1}/{total})", 0.0))
            self.events.put(("current", 0.0, "Preparando audio…"))

            def progress(value: float, preview: str) -> None:
                self.events.put(("current", value, preview))

            try:
                try:
                    result = transcriber.transcribe_file(
                        path, language=options["language_code"],
                        progress_callback=progress, cancel_event=self.cancel_event,
                        initial_prompt=options.get("dictionary_prompt"),
                    )
                except Exception as exc:
                    if options.get("device") != "cpu" and is_cuda_runtime_error(exc):
                        transcriber = self._activate_cpu_fallback(options, exc)
                        self.events.put(("file", index, "Reintentando en CPU"))
                        result = transcriber.transcribe_file(
                            path, language=options["language_code"],
                            progress_callback=progress, cancel_event=self.cancel_event,
                            initial_prompt=options.get("dictionary_prompt"),
                        )
                    else:
                        raise

                speaker_options = options.get("speaker_options", {})
                if speaker_options.get("enabled"):
                    self.events.put(("phase", f"Etapa 4/6 · Identificando personas en {path.name}…", None))
                    result = self._speaker_diarizer.process(
                        result,
                        token=str(speaker_options.get("token", "")),
                        device=options.get("device", "auto"),
                        expected_people=speaker_options.get("expected_people"),
                        status_callback=lambda text: self.events.put(("phase", f"Etapa 4/6 · {text}", None)),
                    )
                else:
                    self.events.put(("phase", "Etapa 4/6 · Identificación de personas omitida.", None))

                self.events.put(("phase", f"Etapa 5/6 · Creando documentos de {path.name}…", 0.99))
                written = export_research_result(
                    result, options["output"], options["formats"],
                    content_options=options["content_options"],
                )
                self._record_processed(path, written)
                self._on_result_ready(result, written)
                success += 1
                self.events.put(("file", index, "Completado"))
                self.events.put(("current", 1.0, "Documentos completados."))
            except TranscriptionCancelled:
                self.events.put(("file", index, "Cancelado"))
                break
            except Exception as exc:
                errors += 1
                report = self._create_error_report(path, exc, options, traceback.format_exc())
                self.events.put(("file", index, "Error"))
                self.events.put(("error_detail", report))
            self.events.put(("batch", (index + 1) / total))

        cancelled = self.cancel_event.is_set()
        self._mark_session_finished(success, errors, cancelled)
        self.events.put(("phase", "Etapa 6/6 · Finalizando el lote…", 1.0))
        self._terminal_event_queued = True
        self.events.put(("finished", success, errors, cancelled, options["output"]))
