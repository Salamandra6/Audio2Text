from __future__ import annotations

import gc
import os
import platform
import queue
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import messagebox

import customtkinter as ctk

from .app import BASE, BORDER, CARD, CONTROL, ERROR, HOVER, MUTED, WHITE, YELLOW
from .exporters import export_result
from .scrollable_app import Audio2TextApp as ScrollableAudio2TextApp
from .transcriber import AudioTranscriber, TranscriptionCancelled

PERFORMANCE_PROFILES = {
    "Automático": "auto",
    "Rápido": "fast",
    "Equilibrado": "balanced",
    "Preciso": "accurate",
}


class Audio2TextApp(ScrollableAudio2TextApp):
    """Interfaz desplazable con actividad visible, diagnóstico y modo adaptable."""

    def __init__(self) -> None:
        super().__init__()
        self._transcriber_cache: tuple[tuple[str, ...], AudioTranscriber] | None = None
        self._running = False
        self._run_started_at = 0.0
        self._last_worker_activity = 0.0
        self._worker_stopped_seen_at: float | None = None
        self._error_popup_shown = False
        self.last_error_text = ""
        self.last_error_log: Path | None = None
        self.after(1000, self._update_activity_clock)

    def _build_ui(self) -> None:
        super()._build_ui()

        self.performance_profile = tk.StringVar(value="Automático")

        diagnostics = self._card(self.main_scroll)
        diagnostics.grid(row=2, column=0, sticky="ew", padx=28, pady=(0, 28))
        diagnostics.grid_columnconfigure(0, weight=1)
        diagnostics.grid_columnconfigure(1, minsize=250)

        ctk.CTkLabel(
            diagnostics,
            text="Rendimiento y diagnóstico",
            text_color=WHITE,
            anchor="w",
            font=self._font(17, True),
        ).grid(row=0, column=0, sticky="ew", padx=18, pady=(17, 0))
        ctk.CTkLabel(
            diagnostics,
            text="Muestra actividad continua, tiempo transcurrido y detalles técnicos de los errores.",
            text_color=MUTED,
            anchor="w",
            font=self._font(10),
        ).grid(row=1, column=0, sticky="ew", padx=18, pady=(3, 14))

        ctk.CTkLabel(
            diagnostics,
            text="Perfil",
            text_color=MUTED,
            anchor="w",
            font=self._font(10),
        ).grid(row=0, column=1, sticky="ew", padx=(8, 18), pady=(17, 3))
        self.performance_box = ctk.CTkOptionMenu(
            diagnostics,
            variable=self.performance_profile,
            values=list(PERFORMANCE_PROFILES),
            fg_color=CONTROL,
            button_color=HOVER,
            button_hover_color=YELLOW,
            dropdown_fg_color=CONTROL,
            dropdown_hover_color=HOVER,
            dropdown_text_color=WHITE,
            text_color=WHITE,
            corner_radius=12,
            height=38,
            anchor="w",
            font=self._font(11),
            dropdown_font=self._font(11),
        )
        self.performance_box.grid(row=1, column=1, sticky="ew", padx=(8, 18), pady=(0, 14))

        activity = ctk.CTkFrame(
            diagnostics,
            fg_color=BASE,
            corner_radius=16,
            border_width=1,
            border_color=BORDER,
        )
        activity.grid(row=2, column=0, columnspan=2, sticky="ew", padx=18, pady=(0, 12))
        activity.grid_columnconfigure(0, weight=1)

        self.activity_state_label = ctk.CTkLabel(
            activity,
            text="EN ESPERA",
            text_color=MUTED,
            anchor="w",
            font=self._font(10, True),
        )
        self.activity_state_label.grid(row=0, column=0, sticky="w", padx=14, pady=(12, 0))

        self.activity_percent_label = ctk.CTkLabel(
            activity,
            text="0%",
            text_color=YELLOW,
            anchor="e",
            font=self._font(12, True),
        )
        self.activity_percent_label.grid(row=0, column=1, sticky="e", padx=14, pady=(12, 0))

        self.activity_phase_label = ctk.CTkLabel(
            activity,
            text="Agrega un archivo para comenzar.",
            text_color=WHITE,
            anchor="w",
            justify="left",
            wraplength=780,
            font=self._font(11),
        )
        self.activity_phase_label.grid(
            row=1, column=0, columnspan=2, sticky="ew", padx=14, pady=(4, 8)
        )

        self.activity_spinner = ctk.CTkProgressBar(
            activity,
            mode="indeterminate",
            fg_color=CONTROL,
            progress_color=YELLOW,
            corner_radius=8,
            height=9,
            indeterminate_speed=0.8,
        )
        self.activity_spinner.grid(
            row=2, column=0, columnspan=2, sticky="ew", padx=14, pady=(0, 8)
        )
        self.activity_spinner.set(0)

        self.activity_clock_label = ctk.CTkLabel(
            activity,
            text="Tiempo: 00:00 · Sin actividad iniciada",
            text_color=MUTED,
            anchor="w",
            font=self._font(9),
        )
        self.activity_clock_label.grid(
            row=3, column=0, columnspan=2, sticky="ew", padx=14, pady=(0, 12)
        )

        ctk.CTkLabel(
            diagnostics,
            text=self._hardware_hint(),
            text_color=MUTED,
            anchor="w",
            justify="left",
            wraplength=800,
            font=self._font(9),
        ).grid(row=3, column=0, sticky="ew", padx=18, pady=(0, 18))

        self.error_button = ctk.CTkButton(
            diagnostics,
            text="Ver último error",
            command=self._show_last_error,
            state="disabled",
            fg_color="transparent",
            hover_color=HOVER,
            text_color=WHITE,
            border_color=BORDER,
            border_width=1,
            corner_radius=12,
            height=38,
            font=self._font(10, True),
        )
        self.error_button.grid(row=3, column=1, sticky="ew", padx=(8, 18), pady=(0, 18))

    @staticmethod
    def _hardware_hint() -> str:
        cores = max(1, os.cpu_count() or 1)
        if cores <= 4:
            return (
                f"Equipo detectado: {cores} núcleos lógicos. Recomendación: perfil Automático "
                "y modelo base o tiny para mantener Windows responsivo."
            )
        return (
            f"Equipo detectado: {cores} núcleos lógicos. El perfil Automático limita los hilos "
            "para evitar que la interfaz y Windows se congelen."
        )

    def _start(self) -> None:
        if not self.files:
            messagebox.showwarning("Sin archivos", "Agrega al menos un archivo.")
            return

        selected_formats = [name for name, variable in self.formats.items() if variable.get()]
        if not selected_formats:
            messagebox.showwarning("Sin formato", "Selecciona al menos un formato de salida.")
            return

        output = Path(self.output_dir.get()).expanduser()
        try:
            output.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            messagebox.showerror("Carpeta inválida", str(exc))
            return

        self.cancel_event.clear()
        self.current_progress.set(0)
        self.batch_progress.set(0)
        for index in range(len(self.files)):
            self._set_file_status(index, "Pendiente")

        self.last_error_text = ""
        self.last_error_log = None
        self._error_popup_shown = False
        self.error_button.configure(state="disabled")
        self._running = True
        self._run_started_at = time.monotonic()
        self._last_worker_activity = self._run_started_at
        self._worker_stopped_seen_at = None
        self._set_activity("Preparando el proceso…", None)
        self._set_running(True)

        options = {
            "files": list(self.files),
            "formats": selected_formats,
            "output": output,
            "model": self.model.get(),
            "language": self.language.get(),
            "language_code": self._language_code(),
            "device": self.device.get(),
            "compute": self.compute.get(),
            "profile": PERFORMANCE_PROFILES[self.performance_profile.get()],
            "profile_label": self.performance_profile.get(),
        }
        self.worker = threading.Thread(
            target=self._run_batch,
            args=(options,),
            daemon=True,
            name="Audio2TextWorker",
        )
        self.worker.start()

    def _language_code(self) -> str | None:
        from .app import LANGUAGES

        return LANGUAGES[self.language.get()]

    def _run_batch(self, options: dict) -> None:
        cache_key = (
            options["model"],
            options["device"],
            options["compute"],
            options["profile"],
        )

        try:
            if self._transcriber_cache and self._transcriber_cache[0] == cache_key:
                transcriber = self._transcriber_cache[1]
                self.events.put(("phase", "Modelo reutilizado desde la memoria. Iniciando audio…", None))
            else:
                if self._transcriber_cache:
                    self._transcriber_cache = None
                    gc.collect()
                self.events.put(("phase", "Cargando el modelo. La primera vez puede tardar por la descarga…", None))
                transcriber = AudioTranscriber(
                    options["model"],
                    options["device"],
                    options["compute"],
                    performance_profile=options["profile"],
                    status_callback=lambda text: self.events.put(("phase", text, None)),
                )
                self._transcriber_cache = (cache_key, transcriber)
        except Exception as exc:
            report = self._create_error_report(None, exc, options, traceback.format_exc())
            self.events.put(("error_detail", report))
            self.events.put(("fatal", f"No se pudo cargar el modelo: {type(exc).__name__}: {exc}"))
            return

        success = errors = 0
        total = len(options["files"])
        for index, path in enumerate(options["files"]):
            if self.cancel_event.is_set():
                break

            self.events.put(("file", index, "Procesando"))
            self.events.put(("phase", f"Procesando {path.name} ({index + 1}/{total})", 0.0))
            self.events.put(("current", 0.0, "Preparando audio…"))

            def progress(value: float, preview: str) -> None:
                self.events.put(("current", value, preview))

            try:
                result = transcriber.transcribe_file(
                    path,
                    language=options["language_code"],
                    progress_callback=progress,
                    cancel_event=self.cancel_event,
                )
                self.events.put(("phase", f"Guardando resultados de {path.name}…", 0.99))
                export_result(result, options["output"], options["formats"])
                success += 1
                self.events.put(("file", index, "Completado"))
                self.events.put(("current", 1.0, "Archivo completado."))
            except TranscriptionCancelled:
                self.events.put(("file", index, "Cancelado"))
                break
            except Exception as exc:
                errors += 1
                report = self._create_error_report(path, exc, options, traceback.format_exc())
                self.events.put(("file", index, "Error"))
                self.events.put(("error_detail", report))

            self.events.put(("batch", (index + 1) / total))

        self.events.put(("finished", success, errors, self.cancel_event.is_set(), options["output"]))

    def _create_error_report(self, path: Path | None, exc: Exception, options: dict, trace: str) -> dict:
        error_type = type(exc).__name__
        message = str(exc).strip() or "La biblioteca no entregó un mensaje adicional."
        friendly = self._friendly_error(error_type, message)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        report_text = (
            "Audio2Text - Informe de error\n"
            f"Fecha: {timestamp}\n"
            f"Archivo: {path if path else 'Carga del modelo'}\n"
            f"Tipo: {error_type}\n"
            f"Mensaje: {message}\n"
            f"Sugerencia: {friendly}\n\n"
            "Configuración\n"
            f"Modelo: {options.get('model')}\n"
            f"Idioma: {options.get('language')}\n"
            f"Dispositivo: {options.get('device')}\n"
            f"Precisión: {options.get('compute')}\n"
            f"Perfil: {options.get('profile_label')}\n\n"
            "Sistema\n"
            f"Windows/Sistema: {platform.platform()}\n"
            f"Python: {sys.version}\n"
            f"Núcleos lógicos: {os.cpu_count()}\n\n"
            "Detalle técnico\n"
            f"{trace}"
        )

        log_path = self._write_error_log(options.get("output"), report_text)
        return {
            "file": str(path) if path else "Carga del modelo",
            "type": error_type,
            "message": message,
            "friendly": friendly,
            "trace": trace,
            "log_path": str(log_path) if log_path else "No se pudo escribir el registro.",
        }

    @staticmethod
    def _friendly_error(error_type: str, message: str) -> str:
        text = f"{error_type} {message}".lower()
        if "cuda" in text or "cublas" in text or "cudnn" in text:
            return "Prueba Dispositivo: cpu y Precisión: int8. Revisa también el controlador NVIDIA."
        if "out of memory" in text or "bad allocation" in text or "memoryerror" in text:
            return "No hay memoria suficiente. Usa modelo tiny o base, perfil Rápido y CPU/int8."
        if "invalid data" in text or "could not open" in text or "averror" in text:
            return "El archivo puede estar dañado o usar un códec no compatible. Prueba convertirlo a WAV o MP3."
        if "connection" in text or "timeout" in text or "huggingface" in text or "download" in text:
            return "La descarga inicial del modelo falló. Comprueba Internet, espacio en disco y vuelve a intentar."
        if "permission" in text or "access is denied" in text:
            return "Windows bloqueó el acceso. Elige otra carpeta de salida o ejecuta desde una carpeta del usuario."
        if "empty" in text or "vacío" in text:
            return "El archivo no contiene datos de audio utilizables."
        return "Revisa el detalle técnico y el registro. También prueba perfil Rápido, modelo base y CPU/int8."

    @staticmethod
    def _write_error_log(output: Path | str | None, report_text: str) -> Path | None:
        candidates = []
        if output:
            candidates.append(Path(output).expanduser() / "Audio2Text_logs")
        candidates.append(Path.home() / "Documents" / "Audio2Text" / "logs")

        filename = f"error_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.log"
        for directory in candidates:
            try:
                directory.mkdir(parents=True, exist_ok=True)
                path = directory / filename
                path.write_text(report_text, encoding="utf-8")
                return path
            except OSError:
                continue
        return None

    def _drain_events(self) -> None:
        try:
            while True:
                event = self.events.get_nowait()
                kind = event[0]
                self._last_worker_activity = time.monotonic()

                if kind == "status":
                    self._set_status(event[1])
                    self._set_activity(event[1], None)
                elif kind == "phase":
                    _, text, progress = event
                    self._set_status(text)
                    self._set_activity(text, progress)
                elif kind == "file":
                    self._set_file_status(event[1], event[2])
                elif kind == "current":
                    _, value, preview = event
                    value = max(0.0, min(1.0, float(value)))
                    self.current_progress.set(value)
                    text = preview.strip() if preview else self.activity_phase_label.cget("text")
                    self._set_activity(text, value)
                elif kind == "batch":
                    self.batch_progress.set(max(0.0, min(1.0, float(event[1]))))
                elif kind == "error_detail":
                    self._handle_error(event[1])
                elif kind == "fatal":
                    self._running = False
                    self._set_running(False)
                    self._set_status(event[1])
                    self._finish_activity("DETENIDO POR ERROR", event[1], ERROR)
                    if not self._error_popup_shown:
                        messagebox.showerror("Error", event[1])
                        self._error_popup_shown = True
                elif kind == "finished":
                    _, success, errors, cancelled, output = event
                    self._running = False
                    self._set_running(False)
                    word = "cancelado" if cancelled else "terminado"
                    summary = f"Proceso {word}. Completados: {success}; errores: {errors}."
                    self._set_status(summary)
                    state = "CANCELADO" if cancelled else ("TERMINADO CON ERRORES" if errors else "COMPLETADO")
                    color = ERROR if errors else (MUTED if cancelled else YELLOW)
                    self._finish_activity(state, summary, color)
                    if not cancelled:
                        extra = "\n\nUsa ‘Ver último error’ para revisar el detalle." if errors else ""
                        messagebox.showinfo(
                            "Proceso terminado",
                            f"Completados: {success}\nErrores: {errors}\n\nResultados en:\n{output}{extra}",
                        )
        except queue.Empty:
            pass
        self.after(100, self._drain_events)

    def _set_activity(self, text: str, progress: float | None) -> None:
        self.activity_state_label.configure(text="EN PROCESO", text_color=YELLOW)
        self.activity_phase_label.configure(text=text)
        self.activity_percent_label.configure(
            text="Preparando…" if progress is None else f"{round(progress * 100)}%"
        )
        self._last_worker_activity = time.monotonic()

    def _finish_activity(self, state: str, text: str, color: str) -> None:
        self.activity_spinner.stop()
        self.activity_spinner.set(1 if state == "COMPLETADO" else 0)
        self.activity_state_label.configure(text=state, text_color=color)
        self.activity_phase_label.configure(text=text)
        if state == "COMPLETADO":
            self.activity_percent_label.configure(text="100%")

    def _set_running(self, running: bool) -> None:
        super()._set_running(running)
        if hasattr(self, "performance_box"):
            self.performance_box.configure(state="disabled" if running else "normal")
        if hasattr(self, "activity_spinner"):
            if running:
                self.activity_spinner.configure(mode="indeterminate")
                self.activity_spinner.start()
            else:
                self.activity_spinner.stop()

    def _update_activity_clock(self) -> None:
        if self._running:
            now = time.monotonic()
            elapsed = max(0, int(now - self._run_started_at))
            idle = max(0, int(now - self._last_worker_activity))
            minutes, seconds = divmod(elapsed, 60)
            alive = bool(self.worker and self.worker.is_alive())

            if alive:
                self._worker_stopped_seen_at = None
                if idle >= 45:
                    signal = f"Sin avances visibles hace {idle} s. Puede estar descargando o cargando el modelo."
                    self.activity_state_label.configure(text="ESPERANDO RESPUESTA", text_color=YELLOW)
                else:
                    signal = f"Última señal del proceso hace {idle} s"
                self.activity_clock_label.configure(
                    text=f"Tiempo: {minutes:02d}:{seconds:02d} · {signal}"
                )
            else:
                if self._worker_stopped_seen_at is None:
                    self._worker_stopped_seen_at = now
                elif now - self._worker_stopped_seen_at >= 2:
                    self._running = False
                    self._set_running(False)
                    text = "El proceso se detuvo sin entregar un resultado. Revisa el último error o vuelve a intentar."
                    self._set_status(text)
                    self._finish_activity("DETENIDO", text, ERROR)
        self.after(1000, self._update_activity_clock)

    def _handle_error(self, report: dict) -> None:
        self.last_error_log = (
            Path(report["log_path"]) if report["log_path"] != "No se pudo escribir el registro." else None
        )
        self.last_error_text = (
            f"Archivo: {report['file']}\n"
            f"Tipo: {report['type']}\n"
            f"Mensaje: {report['message']}\n"
            f"Sugerencia: {report['friendly']}\n"
            f"Registro: {report['log_path']}\n\n"
            f"Detalle técnico:\n{report['trace']}"
        )
        self.error_button.configure(state="normal")
        self._set_status(f"Error {report['type']}: {report['message']}")
        self._set_activity(f"Error {report['type']}: {report['message']}", None)

        if not self._error_popup_shown:
            messagebox.showerror(
                "Audio2Text encontró un error",
                f"Archivo: {report['file']}\n\n"
                f"Tipo: {report['type']}\n"
                f"Mensaje: {report['message']}\n\n"
                f"Qué probar:\n{report['friendly']}\n\n"
                f"Registro:\n{report['log_path']}",
            )
            self._error_popup_shown = True

    def _show_last_error(self) -> None:
        if not self.last_error_text:
            messagebox.showinfo("Sin errores", "Todavía no hay un error registrado en esta sesión.")
            return

        window = ctk.CTkToplevel(self)
        window.title("Detalle del último error")
        window.geometry("780x560")
        window.minsize(620, 420)
        window.configure(fg_color=BASE)
        window.grid_columnconfigure(0, weight=1)
        window.grid_rowconfigure(1, weight=1)
        window.transient(self)

        ctk.CTkLabel(
            window,
            text="Detalle técnico del último error",
            text_color=WHITE,
            anchor="w",
            font=self._font(19, True),
        ).grid(row=0, column=0, sticky="ew", padx=20, pady=(18, 10))

        textbox = ctk.CTkTextbox(
            window,
            fg_color=CARD,
            text_color=WHITE,
            border_width=1,
            border_color=BORDER,
            corner_radius=14,
            font=self._font(10),
            wrap="word",
        )
        textbox.grid(row=1, column=0, sticky="nsew", padx=20, pady=(0, 12))
        textbox.insert("1.0", self.last_error_text)
        textbox.configure(state="disabled")

        buttons = ctk.CTkFrame(window, fg_color="transparent")
        buttons.grid(row=2, column=0, sticky="e", padx=20, pady=(0, 18))
        ctk.CTkButton(
            buttons,
            text="Copiar detalle",
            command=self._copy_last_error,
            fg_color=YELLOW,
            hover_color="#ffe04d",
            text_color=BASE,
            corner_radius=12,
            font=self._font(10, True),
        ).pack(side="left", padx=(0, 8))
        ctk.CTkButton(
            buttons,
            text="Abrir carpeta del registro",
            command=self._open_error_folder,
            state="normal" if self.last_error_log else "disabled",
            fg_color=CONTROL,
            hover_color=HOVER,
            text_color=WHITE,
            corner_radius=12,
            font=self._font(10, True),
        ).pack(side="left")

    def _copy_last_error(self) -> None:
        self.clipboard_clear()
        self.clipboard_append(self.last_error_text)
        self.update_idletasks()

    def _open_error_folder(self) -> None:
        if not self.last_error_log:
            return
        try:
            os.startfile(self.last_error_log.parent)  # type: ignore[attr-defined]
        except OSError as exc:
            messagebox.showerror("No se pudo abrir la carpeta", str(exc))


def run() -> None:
    Audio2TextApp().mainloop()
