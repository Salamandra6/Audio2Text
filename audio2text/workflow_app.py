from __future__ import annotations

import threading
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import messagebox

import customtkinter as ctk

from . import __version__
from .app import BASE, BORDER, CONTROL, HOVER, MUTED, WHITE, YELLOW
from .preflight import has_blocking_errors, recommended_settings, run_preflight
from .research_app import Audio2TextApp as ResearchAudio2TextApp
from .state_store import clear_session, find_processed, load_session, remember_processed, save_session
from .update_checker import check_for_update


class Audio2TextApp(ResearchAudio2TextApp):
    """Flujo investigativo con diagnóstico, recuperación y configuración asistida."""

    def __init__(self) -> None:
        self._restoring_session = False
        super().__init__()
        self.after(350, self._restore_session)
        self.after(2500, self._check_updates_async)

    def _build_ui(self) -> None:
        super()._build_ui()
        self.configuration_mode = tk.StringVar(value="Automática recomendada")
        self.dictionary_enabled = tk.BooleanVar(value=False)
        self.dictionary_text = tk.StringVar(value="")
        self.post_correction = tk.BooleanVar(value=True)

        card = self._card(self.main_scroll)
        card.grid(row=4, column=0, sticky="ew", padx=28, pady=(0, 28))
        card.grid_columnconfigure(0, weight=1)
        card.grid_columnconfigure(1, minsize=330)

        ctk.CTkLabel(
            card, text="Preparación y recuperación", text_color=WHITE,
            anchor="w", font=self._font(17, True),
        ).grid(row=0, column=0, sticky="ew", padx=18, pady=(17, 0))
        self.workflow_hint = ctk.CTkLabel(
            card,
            text="La configuración automática adapta modelo, dispositivo y precisión al equipo.",
            text_color=MUTED, anchor="w", justify="left", wraplength=760,
            font=self._font(10),
        )
        self.workflow_hint.grid(row=1, column=0, sticky="ew", padx=18, pady=(3, 12))

        ctk.CTkLabel(
            card, text="Configuración", text_color=MUTED,
            anchor="w", font=self._font(10),
        ).grid(row=0, column=1, sticky="ew", padx=(8, 18), pady=(17, 3))
        self.configuration_mode_box = ctk.CTkOptionMenu(
            card, variable=self.configuration_mode,
            values=["Automática recomendada", "Manual"],
            command=self._on_configuration_mode,
            fg_color=CONTROL, button_color=HOVER, button_hover_color=YELLOW,
            dropdown_fg_color=CONTROL, dropdown_hover_color=HOVER,
            dropdown_text_color=WHITE, text_color=WHITE, corner_radius=12,
            height=38, anchor="w", font=self._font(11), dropdown_font=self._font(11),
        )
        self.configuration_mode_box.grid(row=1, column=1, sticky="ew", padx=(8, 18), pady=(0, 12))

        dictionary = ctk.CTkFrame(
            card, fg_color=BASE, corner_radius=16, border_width=1, border_color=BORDER,
        )
        dictionary.grid(row=2, column=0, columnspan=2, sticky="ew", padx=18, pady=(0, 12))
        dictionary.grid_columnconfigure(1, weight=1)
        self.dictionary_switch = ctk.CTkSwitch(
            dictionary, text="Diccionario personalizado", variable=self.dictionary_enabled,
            command=self._toggle_dictionary, onvalue=True, offvalue=False,
            progress_color=YELLOW, button_color=WHITE, button_hover_color=WHITE,
            fg_color=CONTROL, text_color=WHITE, font=self._font(10, True),
        )
        self.dictionary_switch.grid(row=0, column=0, sticky="w", padx=14, pady=14)
        self.dictionary_entry = ctk.CTkEntry(
            dictionary, textvariable=self.dictionary_text,
            placeholder_text="Nombres, siglas y términos separados por comas",
            state="disabled", fg_color=CONTROL, border_color=BORDER,
            text_color=WHITE, corner_radius=12, height=38, font=self._font(10),
        )
        self.dictionary_entry.grid(row=0, column=1, sticky="ew", padx=(4, 14), pady=14)

        controls = ctk.CTkFrame(card, fg_color="transparent")
        controls.grid(row=3, column=0, columnspan=2, sticky="ew", padx=18, pady=(0, 18))
        controls.grid_columnconfigure(0, weight=1)
        self.correction_switch = ctk.CTkSwitch(
            controls, text="Corrección posterior conservadora",
            variable=self.post_correction, onvalue=True, offvalue=False,
            progress_color=YELLOW, button_color=WHITE, button_hover_color=WHITE,
            fg_color=CONTROL, text_color=WHITE, font=self._font(10, True),
        )
        self.correction_switch.grid(row=0, column=0, sticky="w")
        self.preflight_button = ctk.CTkButton(
            controls, text="Ejecutar diagnóstico", command=self._show_preflight,
            fg_color=CONTROL, hover_color=HOVER, text_color=WHITE,
            border_color=BORDER, border_width=1, corner_radius=12,
            height=38, font=self._font(10, True),
        )
        self.preflight_button.grid(row=0, column=1, sticky="e")
        self.after_idle(lambda: self._on_configuration_mode(self.configuration_mode.get()))

    def _on_configuration_mode(self, selected: str) -> None:
        automatic = selected == "Automática recomendada"
        if automatic:
            settings = recommended_settings()
            self.model.set(settings["model"])
            self.device.set(settings["device"])
            self.compute.set(settings["compute"])
            self.performance_profile.set(settings["profile"])
            self.workflow_hint.configure(text=settings["reason"])
        state = "disabled" if automatic or getattr(self, "_running", False) else "normal"
        for widget in (self.model_box, self.device_box, self.compute_box, self.performance_box):
            widget.configure(state=state)

    def _toggle_dictionary(self) -> None:
        state = "normal" if self.dictionary_enabled.get() and not self._running else "disabled"
        self.dictionary_entry.configure(state=state)

    def _current_options(self) -> dict:
        options = super()._current_options()
        prompt = self.dictionary_text.get().strip() if self.dictionary_enabled.get() else ""
        options["dictionary_prompt"] = prompt or None
        options["content_options"]["correction"] = self.post_correction.get()
        return options

    def _show_preflight(self, indexes: list[int] | None = None) -> bool:
        if not self.files:
            messagebox.showwarning("Sin archivos", "Agrega al menos un archivo para ejecutar el diagnóstico.")
            return False
        target_indexes = list(indexes) if indexes is not None else self._selected_file_indexes()
        paths = [self.files[index] for index in target_indexes]
        if not paths:
            messagebox.showwarning("Sin archivos seleccionados", "Marca al menos un archivo o deja todas las casillas vacías para revisar toda la cola.")
            return False
        results = run_preflight(paths, Path(self.output_dir.get()).expanduser(), self.device.get())
        symbols = {"ok": "✓", "warning": "!", "error": "✗"}
        visible = results[:25]
        text = "\n".join(f"{symbols[item.level]} {item.title}: {item.detail}" for item in visible)
        if len(results) > len(visible):
            text += f"\n… y {len(results) - len(visible)} resultado(s) más."
        if has_blocking_errors(results):
            messagebox.showerror("Diagnóstico con errores", text)
            return False
        return messagebox.askokcancel(
            "Diagnóstico correcto",
            f"Se procesarán {len(paths)} archivo(s).\n\n{text}\n\n¿Continuar con el procesamiento?",
        )

    def _start(self) -> None:
        if self.configuration_mode.get() == "Automática recomendada":
            self._on_configuration_mode("Automática recomendada")

        run_indexes = self._selected_file_indexes()
        filtered_indexes = self._handle_duplicates(run_indexes)
        if filtered_indexes is None or not filtered_indexes:
            return

        self._run_file_indexes_override = filtered_indexes
        try:
            self._set_activity("Etapa 1/5 · Comprobando archivos y carpeta de destino…", None)
            if not self._show_preflight(filtered_indexes):
                return
            self._save_session(in_progress=True)
            super()._start()
        finally:
            # super()._start() ya creó una copia de las opciones para el hilo.
            self._run_file_indexes_override = None

    def _handle_duplicates(self, indexes: list[int]) -> list[int] | None:
        formats = [name for name, variable in self.formats.items() if variable.get()]
        output = Path(self.output_dir.get()).expanduser()
        duplicates = [
            (index, self.files[index])
            for index in indexes
            if find_processed(self.files[index], output_dir=output, formats=formats)
        ]
        if not duplicates:
            return list(indexes)

        names = "\n".join(f"• {path.name}" for _, path in duplicates[:10])
        answer = messagebox.askyesnocancel(
            "Resultados existentes",
            f"Se encontraron {len(duplicates)} archivo(s) seleccionados con resultados existentes "
            f"en la carpeta de destino actual:\n\n{names}\n\n"
            "Sí: omitirlos solo en esta ejecución.\n"
            "No: procesarlos nuevamente y crear archivos nuevos.\n"
            "Cancelar: volver.",
        )
        if answer is None:
            return None
        if not answer:
            return list(indexes)

        duplicate_indexes = {index for index, _ in duplicates}
        pending = [index for index in indexes if index not in duplicate_indexes]
        if not pending:
            messagebox.showinfo(
                "Sin archivos pendientes",
                "Todos los archivos elegidos tienen resultados existentes.\n\n"
                "No se quitó ni borró ningún elemento de la cola.",
            )
        return pending

    def _record_processed(self, path: Path, outputs: list[Path]) -> None:
        remember_processed(path, outputs)

    def _session_payload(self, in_progress: bool) -> dict:
        return {
            "in_progress": in_progress,
            "files": [str(path) for path in self.files],
            "selected": [variable.get() for variable in self.file_selected],
            "output": self.output_dir.get(),
            "model": self.model.get(),
            "language": self.language.get(),
            "device": self.device.get(),
            "compute": self.compute.get(),
            "profile": self.performance_profile.get(),
            "configuration_mode": self.configuration_mode.get(),
            "formats": {name: value.get() for name, value in self.formats.items()},
            "content_mode": self.content_mode.get(),
            "content_options": {name: value.get() for name, value in self.content_options.items()},
            "dictionary_enabled": self.dictionary_enabled.get(),
            "dictionary_text": self.dictionary_text.get(),
            "post_correction": self.post_correction.get(),
        }

    def _save_session(self, in_progress: bool = False) -> None:
        if self._restoring_session or not hasattr(self, "configuration_mode"):
            return
        save_session(self._session_payload(in_progress))

    def _mark_session_finished(self, success: int, errors: int, cancelled: bool) -> None:
        # Este método se ejecuta en el hilo trabajador: no debe leer variables de Tk.
        if success and not errors and not cancelled:
            clear_session()

    def _restore_session(self) -> None:
        data = load_session()
        paths = [Path(value) for value in data.get("files", []) if Path(value).is_file()]
        if not paths:
            return
        interrupted = bool(data.get("in_progress"))
        title = "Recuperar proceso interrumpido" if interrupted else "Restaurar última sesión"
        if not messagebox.askyesno(title, f"Se encontraron {len(paths)} archivo(s) guardados. ¿Restaurar la sesión?"):
            return
        self._restoring_session = True
        try:
            self.files = paths
            self.file_statuses = ["Pendiente"] * len(paths)
            selected_values = list(data.get("selected", []))
            self.file_selected = [
                tk.BooleanVar(value=bool(selected_values[index]) if index < len(selected_values) else False)
                for index in range(len(paths))
            ]
            for key, variable in (
                ("output", self.output_dir), ("model", self.model), ("language", self.language),
                ("device", self.device), ("compute", self.compute),
                ("profile", self.performance_profile), ("configuration_mode", self.configuration_mode),
                ("content_mode", self.content_mode), ("dictionary_text", self.dictionary_text),
            ):
                if key in data:
                    variable.set(data[key])
            for name, value in data.get("formats", {}).items():
                if name in self.formats:
                    self.formats[name].set(bool(value))
            for name, value in data.get("content_options", {}).items():
                if name in self.content_options:
                    self.content_options[name].set(bool(value))
            self.dictionary_enabled.set(bool(data.get("dictionary_enabled", False)))
            self.post_correction.set(bool(data.get("post_correction", True)))
            self._render_file_rows()
            self._toggle_dictionary()
            self._on_configuration_mode(self.configuration_mode.get())
            self._set_status("Sesión restaurada. Ejecuta el diagnóstico antes de continuar.")
        finally:
            self._restoring_session = False

    def _add_paths(self, paths: list[Path]) -> None:
        super()._add_paths(paths)
        self._save_session()

    def _remove_selected(self) -> None:
        super()._remove_selected()
        self._save_session()

    def _clear(self) -> None:
        super()._clear()
        clear_session()

    def _choose_output(self) -> None:
        super()._choose_output()
        self._save_session()

    def _check_updates_async(self) -> None:
        def worker() -> None:
            try:
                info = check_for_update(__version__)
            except Exception:
                return
            if info.available:
                self.after(0, lambda: self._offer_update(info.version, info.page_url))
        threading.Thread(target=worker, daemon=True, name="Audio2TextUpdateCheck").start()

    def _offer_update(self, version: str, page_url: str) -> None:
        if messagebox.askyesno(
            "Actualización disponible",
            f"Está disponible la versión v{version}. ¿Abrir la página de actualización?",
        ) and page_url:
            webbrowser.open(page_url)

    def _set_running(self, running: bool) -> None:
        super()._set_running(running)
        state = "disabled" if running else "normal"
        for widget in (
            getattr(self, "configuration_mode_box", None),
            getattr(self, "dictionary_switch", None),
            getattr(self, "correction_switch", None),
            getattr(self, "preflight_button", None),
        ):
            if widget is not None:
                widget.configure(state=state)
        if not running:
            self._toggle_dictionary()
            self._on_configuration_mode(self.configuration_mode.get())


def run() -> None:
    Audio2TextApp().mainloop()
