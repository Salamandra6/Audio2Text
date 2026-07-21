from __future__ import annotations

import threading
import time
import traceback
from pathlib import Path
from tkinter import messagebox

from .app import ERROR, LANGUAGES, MUTED, YELLOW
from .enhanced_app import Audio2TextApp as EnhancedAudio2TextApp
from .enhanced_app import PERFORMANCE_PROFILES


class Audio2TextApp(EnhancedAudio2TextApp):
    """Interfaz estable con arranque protegido y diagnóstico garantizado."""

    def __init__(self) -> None:
        self._active_options: dict = {}
        self._dead_worker_seen_at: float | None = None
        self._terminal_event_queued = False
        self._run_file_indexes_override: list[int] | None = None
        super().__init__()

    def _selected_file_indexes(self) -> list[int]:
        selected = [
            index
            for index, variable in enumerate(self.file_selected)
            if variable.get()
        ]
        return selected or list(range(len(self.files)))

    def _current_options(self) -> dict:
        profile_label = self.performance_profile.get()
        indexes = (
            list(self._run_file_indexes_override)
            if self._run_file_indexes_override is not None
            else self._selected_file_indexes()
        )
        return {
            "files": [self.files[index] for index in indexes],
            "file_indices": indexes,
            "formats": [name for name, value in self.formats.items() if value.get()],
            "output": Path(self.output_dir.get()).expanduser(),
            "model": self.model.get(),
            "language": self.language.get(),
            "language_code": LANGUAGES[self.language.get()],
            "device": self.device.get(),
            "compute": self.compute.get(),
            "profile": PERFORMANCE_PROFILES[profile_label],
            "profile_label": profile_label,
        }

    def _start(self) -> None:
        if not self.files:
            messagebox.showwarning("Sin archivos", "Agrega al menos un archivo.")
            return

        options = self._current_options()
        if not options["files"]:
            messagebox.showwarning("Sin archivos seleccionados", "Marca al menos un archivo o deja todas las casillas vacías para procesar la cola completa.")
            return
        if not options["formats"]:
            messagebox.showwarning("Sin formato", "Selecciona al menos un formato de salida.")
            return

        try:
            options["output"].mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            messagebox.showerror("Carpeta inválida", str(exc))
            return

        self.cancel_event.clear()
        self.current_progress.set(0)
        self.batch_progress.set(0)
        for index in options["file_indices"]:
            self._set_file_status(index, "Pendiente")

        self.last_error_text = ""
        self.last_error_log = None
        self._error_popup_shown = False
        self.error_button.configure(state="disabled")
        self._running = True
        self._run_started_at = time.monotonic()
        self._last_worker_activity = self._run_started_at
        self._dead_worker_seen_at = None
        self._terminal_event_queued = False
        self._active_options = dict(options)
        self._set_activity("Preparando el proceso…", None)
        self._set_running(True)

        try:
            self.worker = threading.Thread(
                target=self._safe_run_batch,
                args=(options,),
                daemon=True,
                name="Audio2TextWorker",
            )
            self.worker.start()
        except Exception as exc:
            self._report_startup_failure(exc, options)

    def _safe_run_batch(self, options: dict) -> None:
        try:
            super()._run_batch(options)
        except Exception as exc:
            report = self._create_error_report(
                None,
                exc,
                options,
                traceback.format_exc(),
            )
            self._terminal_event_queued = True
            self.events.put(("error_detail", report))
            self.events.put(("fatal", f"El proceso terminó inesperadamente: {type(exc).__name__}: {exc}"))

    def _report_startup_failure(self, exc: Exception, options: dict) -> None:
        self._running = False
        self._terminal_event_queued = True
        report = self._create_error_report(None, exc, options, traceback.format_exc())
        self._handle_error(report)
        self._set_running(False)
        text = f"No se pudo iniciar el procesamiento: {type(exc).__name__}: {exc}"
        self._set_status(text)
        self._finish_activity("DETENIDO POR ERROR", text, ERROR)

    def _update_activity_clock(self) -> None:
        if self._running:
            now = time.monotonic()
            elapsed = max(0, int(now - self._run_started_at))
            idle = max(0, int(now - self._last_worker_activity))
            minutes, seconds = divmod(elapsed, 60)
            alive = bool(self.worker and self.worker.is_alive())

            if alive:
                self._dead_worker_seen_at = None
                if idle >= 45:
                    signal = f"Sin avances visibles hace {idle} s. Puede estar cargando el modelo."
                    self.activity_state_label.configure(text="ESPERANDO RESPUESTA", text_color=YELLOW)
                else:
                    signal = f"Última señal del proceso hace {idle} s"
                self.activity_clock_label.configure(text=f"Tiempo: {minutes:02d}:{seconds:02d} · {signal}")
            else:
                if self._dead_worker_seen_at is None:
                    self._dead_worker_seen_at = now
                self.activity_clock_label.configure(
                    text=f"Tiempo: {minutes:02d}:{seconds:02d} · Finalizando y recopilando resultado…"
                )

                if now - self._dead_worker_seen_at >= 10:
                    self._running = False
                    self._set_running(False)
                    if self._terminal_event_queued or self.last_error_text:
                        text = (
                            "El proceso terminó después del error informado. "
                            "El diagnóstico principal está disponible en ‘Ver último error’."
                        )
                        self._set_status(text)
                        self._finish_activity("DETENIDO POR ERROR", text, ERROR)
                    else:
                        exc = RuntimeError("El hilo terminó sin emitir un evento final.")
                        report = self._create_error_report(
                            None,
                            exc,
                            self._active_options or self._current_options(),
                            "El monitor detectó un hilo finalizado sin evento finished o fatal.",
                        )
                        self._handle_error(report)
                        text = "El proceso se detuvo. El diagnóstico está disponible en ‘Ver último error’."
                        self._set_status(text)
                        self._finish_activity("DETENIDO POR ERROR", text, ERROR)

        self.after(1000, self._update_activity_clock)


def run() -> None:
    Audio2TextApp().mainloop()
