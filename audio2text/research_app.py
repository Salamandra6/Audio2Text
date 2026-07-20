from __future__ import annotations

import gc
import tkinter as tk
import traceback

import customtkinter as ctk

from .app import BASE, BORDER, CONTROL, HOVER, MUTED, WHITE, YELLOW
from .research_documents import export_research_result
from .stable_app import Audio2TextApp as StableAudio2TextApp
from .prompted_transcriber import PromptedAudioTranscriber
from .transcriber import TranscriptionCancelled


class Audio2TextApp(StableAudio2TextApp):
    """Edición investigativa con documentos y análisis local configurable."""

    def _build_ui(self) -> None:
        super()._build_ui()
        self._replace_formats()
        self._build_content_card()

    def _replace_formats(self) -> None:
        old = list(self.format_switches)
        parent = old[0].master if old else None
        for switch in old:
            switch.destroy()
        self.formats = {
            "docx": tk.BooleanVar(value=True),
            "pdf": tk.BooleanVar(value=False),
            "txt": tk.BooleanVar(value=True),
        }
        self.format_switches = []
        if parent is None:
            return
        for name, variable in self.formats.items():
            switch = ctk.CTkSwitch(
                parent, text={"docx": "WORD", "pdf": "PDF", "txt": "TXT"}[name],
                variable=variable, onvalue=True, offvalue=False,
                progress_color=YELLOW, button_color=WHITE, button_hover_color=WHITE,
                fg_color=CONTROL, text_color=MUTED, font=self._font(10, True),
            )
            switch.pack(side="left", padx=(0, 12))
            self.format_switches.append(switch)

    def _build_content_card(self) -> None:
        self.content_mode = tk.StringVar(value="Literal")
        self.content_options = {
            "timestamps": tk.BooleanVar(value=True),
            "metadata": tk.BooleanVar(value=True),
            "summary": tk.BooleanVar(value=False),
            "topics": tk.BooleanVar(value=False),
        }
        card = self._card(self.main_scroll)
        card.grid(row=3, column=0, sticky="ew", padx=28, pady=(0, 28))
        card.grid_columnconfigure(0, weight=1)
        card.grid_columnconfigure(1, minsize=260)
        ctk.CTkLabel(
            card, text="Contenido del documento", text_color=WHITE,
            anchor="w", font=self._font(17, True),
        ).grid(row=0, column=0, sticky="ew", padx=18, pady=(17, 0))
        ctk.CTkLabel(
            card,
            text="El resumen y los temas se generan localmente, sin enviar información a servicios externos.",
            text_color=MUTED, anchor="w", justify="left", wraplength=850,
            font=self._font(10),
        ).grid(row=1, column=0, sticky="ew", padx=18, pady=(3, 14))
        ctk.CTkLabel(
            card, text="Tipo de transcripción", text_color=MUTED,
            anchor="w", font=self._font(10),
        ).grid(row=0, column=1, sticky="ew", padx=(8, 18), pady=(17, 3))
        self.content_mode_box = ctk.CTkOptionMenu(
            card, variable=self.content_mode, values=["Literal", "Limpia"],
            fg_color=CONTROL, button_color=HOVER, button_hover_color=YELLOW,
            dropdown_fg_color=CONTROL, dropdown_hover_color=HOVER,
            dropdown_text_color=WHITE, text_color=WHITE, corner_radius=12,
            height=38, anchor="w", font=self._font(11), dropdown_font=self._font(11),
        )
        self.content_mode_box.grid(row=1, column=1, sticky="ew", padx=(8, 18), pady=(0, 14))
        frame = ctk.CTkFrame(
            card, fg_color=BASE, corner_radius=16, border_width=1, border_color=BORDER,
        )
        frame.grid(row=2, column=0, columnspan=2, sticky="ew", padx=18, pady=(0, 12))
        for column in range(4):
            frame.grid_columnconfigure(column, weight=1)
        labels = {
            "timestamps": "Marcas de tiempo",
            "metadata": "Informe con metadatos",
            "summary": "Resumen del audio",
            "topics": "Temas principales",
        }
        self.content_switches = []
        for column, (name, variable) in enumerate(self.content_options.items()):
            switch = ctk.CTkSwitch(
                frame, text=labels[name], variable=variable, onvalue=True, offvalue=False,
                progress_color=YELLOW, button_color=WHITE, button_hover_color=WHITE,
                fg_color=CONTROL, text_color=WHITE, font=self._font(10, True),
            )
            switch.grid(row=0, column=column, sticky="w", padx=14, pady=14)
            self.content_switches.append(switch)
        ctk.CTkLabel(
            card,
            text="Literal conserva los segmentos. Limpia normaliza espacios y párrafos sin cambiar el sentido.",
            text_color=MUTED, anchor="w", justify="left", wraplength=1050,
            font=self._font(9),
        ).grid(row=3, column=0, columnspan=2, sticky="ew", padx=18, pady=(0, 18))

    def _current_options(self) -> dict:
        options = super()._current_options()
        options["content_options"] = {
            "mode": "clean" if self.content_mode.get() == "Limpia" else "literal",
            "timestamps": self.content_options["timestamps"].get(),
            "metadata": self.content_options["metadata"].get(),
            "summary": self.content_options["summary"].get(),
            "topics": self.content_options["topics"].get(),
        }
        return options

    def _safe_run_batch(self, options: dict) -> None:
        key = (options["model"], options["device"], options["compute"], options["profile"])
        try:
            if self._transcriber_cache and self._transcriber_cache[0] == key:
                transcriber = self._transcriber_cache[1]
                self.events.put(("phase", "Etapa 2/5 · Modelo reutilizado. Preparando audio…", None))
            else:
                if self._transcriber_cache:
                    self._transcriber_cache = None
                    gc.collect()
                self.events.put(("phase", "Etapa 2/5 · Cargando el modelo…", None))
                transcriber = PromptedAudioTranscriber(
                    options["model"], options["device"], options["compute"],
                    performance_profile=options["profile"],
                    status_callback=lambda text: self.events.put(("phase", f"Etapa 2/5 · {text}", None)),
                )
                self._transcriber_cache = (key, transcriber)
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
            self.events.put(("phase", f"Etapa 3/5 · Transcribiendo {path.name} ({index + 1}/{total})", 0.0))
            self.events.put(("current", 0.0, "Preparando audio…"))

            def progress(value: float, preview: str) -> None:
                self.events.put(("current", value, preview))

            try:
                result = transcriber.transcribe_file(
                    path, language=options["language_code"],
                    progress_callback=progress, cancel_event=self.cancel_event,
                    initial_prompt=options.get("dictionary_prompt"),
                )
                self.events.put(("phase", f"Etapa 4/5 · Creando documentos de {path.name}…", 0.99))
                written = export_research_result(
                    result, options["output"], options["formats"],
                    content_options=options["content_options"],
                )
                if hasattr(self, "_record_processed"):
                    self._record_processed(path, written)
                if hasattr(self, "_on_result_ready"):
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
        if hasattr(self, "_mark_session_finished"):
            self._mark_session_finished(success, errors, cancelled)
        self.events.put(("phase", "Etapa 5/5 · Finalizando el lote…", 1.0))
        self.events.put(("finished", success, errors, cancelled, options["output"]))

    def _set_running(self, running: bool) -> None:
        super()._set_running(running)
        state = "disabled" if running else "normal"
        if hasattr(self, "content_mode_box"):
            self.content_mode_box.configure(state=state)
        for switch in getattr(self, "content_switches", []):
            switch.configure(state=state)


def run() -> None:
    Audio2TextApp().mainloop()
