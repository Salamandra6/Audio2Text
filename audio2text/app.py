from __future__ import annotations

import queue
import threading
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox

import customtkinter as ctk

from .exporters import export_result
from .transcriber import AudioTranscriber, TranscriptionCancelled

AUDIO_EXTENSIONS = {
    ".wav", ".mp3", ".m4a", ".flac", ".ogg", ".opus", ".aac", ".wma",
    ".mp4", ".mkv", ".mov", ".webm", ".m4v",
}
LANGUAGES = {
    "Automático": None, "Español": "es", "Inglés": "en", "Portugués": "pt",
    "Francés": "fr", "Alemán": "de", "Italiano": "it",
}

BASE = "#00224c"
CARD = "#082f5c"
CONTROL = "#0d3b6e"
HOVER = "#154b82"
WHITE = "#ffffff"
MUTED = "#b8cae0"
YELLOW = "#ffd100"
YELLOW_HOVER = "#ffe04d"
BORDER = "#1d5288"
DISABLED = "#6b829d"
SUCCESS = "#65d39a"
ERROR = "#ff7d8a"
STATUS_COLORS = {
    "Pendiente": ("#153f6c", MUTED),
    "Procesando": (YELLOW, BASE),
    "Completado": (SUCCESS, BASE),
    "Error": (ERROR, BASE),
    "Cancelado": (DISABLED, WHITE),
}

ctk.set_appearance_mode("dark")


class Audio2TextApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__(fg_color=BASE)
        self.title("Audio2Text")
        self.geometry("1180x760")
        self.minsize(1000, 680)

        self.files: list[Path] = []
        self.file_statuses: list[str] = []
        self.file_selected: list[tk.BooleanVar] = []
        self.file_rows: list[dict] = []
        self.events: queue.Queue[tuple] = queue.Queue()
        self.cancel_event = threading.Event()
        self.worker: threading.Thread | None = None

        self.model = tk.StringVar(value="small")
        self.language = tk.StringVar(value="Automático")
        self.device = tk.StringVar(value="auto")
        self.compute = tk.StringVar(value="auto")
        self.output_dir = tk.StringVar(value=str(Path.home() / "Documents" / "Audio2Text"))
        self.formats = {
            "txt": tk.BooleanVar(value=True),
            "srt": tk.BooleanVar(value=True),
            "vtt": tk.BooleanVar(value=False),
            "json": tk.BooleanVar(value=False),
        }

        self._build_ui()
        self._render_file_rows()
        self.after(100, self._drain_events)
        self.protocol("WM_DELETE_WINDOW", self._close)

    @staticmethod
    def _font(size: int, bold: bool = False) -> ctk.CTkFont:
        return ctk.CTkFont(family="Segoe UI", size=size, weight="bold" if bold else "normal")

    @staticmethod
    def _card(parent) -> ctk.CTkFrame:
        return ctk.CTkFrame(
            parent, fg_color=CARD, corner_radius=22, border_width=1, border_color=BORDER
        )

    def _title(self, parent, title: str, subtitle: str, row: int = 0) -> None:
        ctk.CTkLabel(parent, text=title, text_color=WHITE, anchor="w", font=self._font(17, True)).grid(
            row=row, column=0, columnspan=2, sticky="ew", padx=18, pady=(17, 0)
        )
        ctk.CTkLabel(parent, text=subtitle, text_color=MUTED, anchor="w", font=self._font(10)).grid(
            row=row + 1, column=0, columnspan=2, sticky="ew", padx=18, pady=(3, 12)
        )

    def _button(self, parent, text, command, kind="secondary", **grid_options):
        styles = {
            "primary": dict(fg_color=YELLOW, hover_color=YELLOW_HOVER, text_color=BASE, border_width=0),
            "secondary": dict(fg_color=CONTROL, hover_color=HOVER, text_color=WHITE, border_width=0),
            "ghost": dict(fg_color="transparent", hover_color=HOVER, text_color=WHITE, border_width=1),
        }
        button = ctk.CTkButton(
            parent, text=text, command=command, corner_radius=12, height=38,
            border_color=BORDER, font=self._font(11, True), **styles[kind]
        )
        button.grid(**grid_options)
        return button

    def _build_ui(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=28, pady=(24, 18))
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(header, text="AUDIO INTELLIGENCE", text_color=YELLOW, font=self._font(11, True)).grid(
            row=0, column=0, sticky="w"
        )
        ctk.CTkLabel(header, text="Audio2Text", text_color=WHITE, font=self._font(32, True)).grid(
            row=1, column=0, sticky="w", pady=(2, 0)
        )
        ctk.CTkLabel(
            header, text="Transcripción local por lotes, rápida, privada y simple.",
            text_color=MUTED, font=self._font(13)
        ).grid(row=2, column=0, sticky="w", pady=(3, 0))
        ctk.CTkLabel(
            header, text="  Procesamiento local  ", fg_color=CONTROL, text_color=WHITE,
            corner_radius=16, height=32, font=self._font(11, True)
        ).grid(row=1, column=1, rowspan=2, sticky="e")

        content = ctk.CTkFrame(self, fg_color="transparent")
        content.grid(row=1, column=0, sticky="nsew", padx=28, pady=(0, 28))
        content.grid_columnconfigure(0, weight=1)
        content.grid_columnconfigure(1, minsize=352)
        content.grid_rowconfigure(0, weight=1)
        self._build_queue(content)
        self._build_sidebar(content)

    def _build_queue(self, parent) -> None:
        card = self._card(parent)
        card.grid(row=0, column=0, sticky="nsew", padx=(0, 18))
        card.grid_columnconfigure(0, weight=1)
        card.grid_rowconfigure(2, weight=1)

        head = ctk.CTkFrame(card, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew", padx=22, pady=(20, 12))
        head.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(head, text="Cola de archivos", text_color=WHITE, font=self._font(19, True)).grid(
            row=0, column=0, sticky="w"
        )
        ctk.CTkLabel(
            head, text="Selecciona audios individuales o una carpeta completa.",
            text_color=MUTED, font=self._font(11)
        ).grid(row=1, column=0, sticky="w", pady=(3, 0))
        self.file_count_label = ctk.CTkLabel(
            head, text="  0 archivos  ", fg_color=CONTROL, text_color=MUTED,
            corner_radius=14, height=28, font=self._font(10, True)
        )
        self.file_count_label.grid(row=0, column=1, rowspan=2, sticky="e")

        actions = ctk.CTkFrame(card, fg_color="transparent")
        actions.grid(row=1, column=0, sticky="ew", padx=22, pady=(0, 14))
        for column in range(4):
            actions.grid_columnconfigure(column, weight=1)
        self.queue_buttons = [
            self._button(actions, "Agregar archivos", self._add_files, "primary", row=0, column=0, sticky="ew", padx=(0, 5)),
            self._button(actions, "Agregar carpeta", self._add_folder, "secondary", row=0, column=1, sticky="ew", padx=5),
            self._button(actions, "Quitar seleccionados", self._remove_selected, "ghost", row=0, column=2, sticky="ew", padx=5),
            self._button(actions, "Limpiar", self._clear, "ghost", row=0, column=3, sticky="ew", padx=(5, 0)),
        ]

        self.file_scroll = ctk.CTkScrollableFrame(
            card, fg_color=BASE, corner_radius=18, border_width=1, border_color=BORDER,
            scrollbar_button_color=HOVER, scrollbar_button_hover_color=YELLOW
        )
        self.file_scroll.grid(row=2, column=0, sticky="nsew", padx=22, pady=(0, 22))
        self.file_scroll.grid_columnconfigure(0, weight=1)

    def _build_sidebar(self, parent) -> None:
        sidebar = ctk.CTkFrame(parent, fg_color="transparent")
        sidebar.grid(row=0, column=1, sticky="nsew")
        sidebar.grid_columnconfigure(0, weight=1)

        settings = self._card(sidebar)
        settings.grid(row=0, column=0, sticky="ew")
        settings.grid_columnconfigure((0, 1), weight=1)
        self._title(settings, "Configuración", "Ajusta calidad, idioma y rendimiento.")
        self.model_box = self._option(settings, "Modelo", self.model, ("tiny", "base", "small", "medium", "large-v3", "turbo"), 2, 0)
        self.language_box = self._option(settings, "Idioma", self.language, tuple(LANGUAGES), 2, 1)
        self.device_box = self._option(settings, "Dispositivo", self.device, ("auto", "cpu", "cuda"), 4, 0)
        self.compute_box = self._option(settings, "Precisión", self.compute, ("auto", "int8", "float16", "float32"), 4, 1)

        ctk.CTkLabel(settings, text="Formatos de salida", text_color=WHITE, anchor="w", font=self._font(11, True)).grid(
            row=6, column=0, columnspan=2, sticky="ew", padx=18, pady=(14, 8)
        )
        switches = ctk.CTkFrame(settings, fg_color="transparent")
        switches.grid(row=7, column=0, columnspan=2, sticky="ew", padx=18, pady=(0, 18))
        self.format_switches = []
        for name, variable in self.formats.items():
            switch = ctk.CTkSwitch(
                switches, text=name.upper(), variable=variable, onvalue=True, offvalue=False,
                progress_color=YELLOW, button_color=WHITE, button_hover_color=WHITE,
                fg_color=CONTROL, text_color=MUTED, font=self._font(10, True)
            )
            switch.pack(side="left", padx=(0, 10))
            self.format_switches.append(switch)

        destination = self._card(sidebar)
        destination.grid(row=1, column=0, sticky="ew", pady=(14, 0))
        destination.grid_columnconfigure(0, weight=1)
        self._title(destination, "Destino", "Carpeta donde se guardarán los resultados.")
        self.output_entry = ctk.CTkEntry(
            destination, textvariable=self.output_dir, fg_color=CONTROL, border_color=BORDER,
            border_width=1, corner_radius=12, height=40, text_color=WHITE, font=self._font(11)
        )
        self.output_entry.grid(row=2, column=0, sticky="ew", padx=18, pady=(2, 10))
        self.output_button = self._button(
            destination, "Elegir carpeta", self._choose_output, "secondary",
            row=3, column=0, sticky="ew", padx=18, pady=(0, 18)
        )

        progress = self._card(sidebar)
        progress.grid(row=2, column=0, sticky="ew", pady=(14, 0))
        progress.grid_columnconfigure(0, weight=1)
        self._title(progress, "Progreso", "Seguimiento del archivo actual y del lote.")
        ctk.CTkLabel(progress, text="Archivo actual", text_color=MUTED, anchor="w", font=self._font(10)).grid(
            row=2, column=0, sticky="ew", padx=18
        )
        self.current_progress = self._progress(progress, 3)
        ctk.CTkLabel(progress, text="Lote completo", text_color=MUTED, anchor="w", font=self._font(10)).grid(
            row=4, column=0, sticky="ew", padx=18
        )
        self.batch_progress = self._progress(progress, 5)
        self.status_label = ctk.CTkLabel(
            progress, text="Agrega archivos o una carpeta para comenzar.", text_color=MUTED,
            justify="left", anchor="w", wraplength=300, font=self._font(10)
        )
        self.status_label.grid(row=6, column=0, sticky="ew", padx=18, pady=(0, 18))

        buttons = ctk.CTkFrame(sidebar, fg_color="transparent")
        buttons.grid(row=3, column=0, sticky="ew", pady=(14, 0))
        buttons.grid_columnconfigure((0, 1), weight=1)
        self.start_button = ctk.CTkButton(
            buttons, text="Iniciar transcripción", command=self._start, fg_color=YELLOW,
            hover_color=YELLOW_HOVER, text_color=BASE, corner_radius=14, height=46,
            font=self._font(12, True)
        )
        self.start_button.grid(row=0, column=0, sticky="ew", padx=(0, 7))
        self.cancel_button = ctk.CTkButton(
            buttons, text="Cancelar", command=self._cancel, state="disabled",
            fg_color="transparent", hover_color=HOVER, text_color=YELLOW,
            border_color=YELLOW, border_width=1, corner_radius=14, height=46,
            font=self._font(12, True)
        )
        self.cancel_button.grid(row=0, column=1, sticky="ew", padx=(7, 0))

    def _option(self, parent, label, variable, values, row, column):
        padx = (18, 7) if column == 0 else (7, 18)
        ctk.CTkLabel(parent, text=label, text_color=MUTED, anchor="w", font=self._font(10)).grid(
            row=row, column=column, sticky="ew", padx=padx
        )
        option = ctk.CTkOptionMenu(
            parent, variable=variable, values=list(values), fg_color=CONTROL,
            button_color=HOVER, button_hover_color=YELLOW, dropdown_fg_color=CONTROL,
            dropdown_hover_color=HOVER, dropdown_text_color=WHITE, text_color=WHITE,
            corner_radius=12, height=38, anchor="w", font=self._font(11),
            dropdown_font=self._font(11)
        )
        option.grid(row=row + 1, column=column, sticky="ew", padx=padx, pady=(5, 0))
        return option

    def _progress(self, parent, row):
        bar = ctk.CTkProgressBar(
            parent, fg_color=CONTROL, progress_color=YELLOW, corner_radius=8, height=9
        )
        bar.grid(row=row, column=0, sticky="ew", padx=18, pady=(6, 12))
        bar.set(0)
        return bar

    def _render_file_rows(self) -> None:
        for child in self.file_scroll.winfo_children():
            child.destroy()
        self.file_rows.clear()
        total = len(self.files)
        self.file_count_label.configure(text=f"  {total} archivo{'s' if total != 1 else ''}  ")

        if not self.files:
            ctk.CTkLabel(
                self.file_scroll, text="Sin archivos todavía\nAgrega uno o varios audios para comenzar.",
                text_color=MUTED, font=self._font(13), justify="center"
            ).grid(row=0, column=0, sticky="nsew", pady=90)
            return

        for index, path in enumerate(self.files):
            row = ctk.CTkFrame(
                self.file_scroll, fg_color=CARD, corner_radius=15,
                border_width=1, border_color=BORDER
            )
            row.grid(row=index, column=0, sticky="ew", pady=(0, 9), padx=2)
            row.grid_columnconfigure(1, weight=1)
            checkbox = ctk.CTkCheckBox(
                row, text="", variable=self.file_selected[index], width=26,
                checkbox_width=20, checkbox_height=20, corner_radius=6,
                fg_color=YELLOW, hover_color=YELLOW_HOVER,
                border_color=BORDER, checkmark_color=BASE
            )
            checkbox.grid(row=0, column=0, rowspan=2, padx=(14, 8), pady=14)
            ctk.CTkLabel(row, text=path.name, text_color=WHITE, anchor="w", font=self._font(12, True)).grid(
                row=0, column=1, sticky="ew", pady=(12, 0)
            )
            ctk.CTkLabel(row, text=str(path.parent), text_color=MUTED, anchor="w", font=self._font(9)).grid(
                row=1, column=1, sticky="ew", pady=(0, 12)
            )
            bg, fg = STATUS_COLORS[self.file_statuses[index]]
            badge = ctk.CTkLabel(
                row, text=f"  {self.file_statuses[index]}  ", fg_color=bg,
                text_color=fg, corner_radius=12, height=26, font=self._font(9, True)
            )
            badge.grid(row=0, column=2, rowspan=2, padx=14)
            self.file_rows.append({"checkbox": checkbox, "status": badge})

    def _set_status(self, text: str) -> None:
        self.status_label.configure(text=text)

    def _add_paths(self, paths: list[Path]) -> None:
        existing = {str(path.resolve()).lower() for path in self.files}
        added = 0
        for path in sorted(paths, key=lambda item: item.name.lower()):
            key = str(path.resolve()).lower()
            if key in existing or path.suffix.lower() not in AUDIO_EXTENSIONS:
                continue
            self.files.append(path)
            self.file_statuses.append("Pendiente")
            self.file_selected.append(tk.BooleanVar(value=False))
            existing.add(key)
            added += 1
        self._render_file_rows()
        self._set_status(
            f"{len(self.files)} archivo(s) en la cola."
            if added else "No se encontraron archivos nuevos compatibles."
        )

    def _add_files(self) -> None:
        paths = filedialog.askopenfilenames(
            title="Seleccionar audios",
            filetypes=(("Audio y video", "*.wav *.mp3 *.m4a *.flac *.ogg *.opus *.aac *.wma *.mp4 *.mkv *.mov *.webm *.m4v"), ("Todos", "*.*")),
        )
        self._add_paths([Path(path) for path in paths])

    def _add_folder(self) -> None:
        selected = filedialog.askdirectory(title="Seleccionar carpeta con audios")
        if selected:
            self._add_paths([path for path in Path(selected).rglob("*") if path.is_file()])

    def _remove_selected(self) -> None:
        indexes = [i for i, variable in enumerate(self.file_selected) if variable.get()]
        if not indexes:
            self._set_status("Marca uno o más archivos para quitarlos.")
            return
        for index in reversed(indexes):
            self.files.pop(index)
            self.file_statuses.pop(index)
            self.file_selected.pop(index)
        self._render_file_rows()
        self._set_status(f"{len(self.files)} archivo(s) en la cola.")

    def _clear(self) -> None:
        self.files.clear()
        self.file_statuses.clear()
        self.file_selected.clear()
        self._render_file_rows()
        self._set_status("Cola vacía.")

    def _choose_output(self) -> None:
        selected = filedialog.askdirectory(title="Seleccionar carpeta de salida")
        if selected:
            self.output_dir.set(selected)

    def _set_file_status(self, index: int, state: str) -> None:
        if not 0 <= index < len(self.files):
            return
        self.file_statuses[index] = state
        if index < len(self.file_rows):
            bg, fg = STATUS_COLORS.get(state, (CONTROL, MUTED))
            self.file_rows[index]["status"].configure(text=f"  {state}  ", fg_color=bg, text_color=fg)

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
        self._set_running(True)
        options = {
            "files": list(self.files), "formats": selected_formats, "output": output,
            "model": self.model.get(), "language": LANGUAGES[self.language.get()],
            "device": self.device.get(), "compute": self.compute.get(),
        }
        self.worker = threading.Thread(target=self._run_batch, args=(options,), daemon=True)
        self.worker.start()

    def _run_batch(self, options: dict) -> None:
        try:
            transcriber = AudioTranscriber(
                options["model"], options["device"], options["compute"],
                status_callback=lambda text: self.events.put(("status", text)),
            )
        except Exception as exc:
            self.events.put(("fatal", f"No se pudo cargar el modelo: {exc}"))
            return

        success = errors = 0
        total = len(options["files"])
        for index, path in enumerate(options["files"]):
            if self.cancel_event.is_set():
                break
            self.events.put(("file", index, "Procesando"))
            self.events.put(("status", f"Procesando {path.name} ({index + 1}/{total})"))
            self.events.put(("current", 0.0))

            def progress(value: float, preview: str) -> None:
                self.events.put(("current", value))
                if preview:
                    self.events.put(("status", f"{path.name}: {preview[:100]}"))

            try:
                result = transcriber.transcribe_file(
                    path, language=options["language"], progress_callback=progress,
                    cancel_event=self.cancel_event,
                )
                export_result(result, options["output"], options["formats"])
                success += 1
                self.events.put(("file", index, "Completado"))
            except TranscriptionCancelled:
                self.events.put(("file", index, "Cancelado"))
                break
            except Exception as exc:
                errors += 1
                self.events.put(("file", index, "Error"))
                self.events.put(("status", f"Error en {path.name}: {exc}"))
            self.events.put(("batch", (index + 1) / total))

        self.events.put(("finished", success, errors, self.cancel_event.is_set(), options["output"]))

    def _drain_events(self) -> None:
        try:
            while True:
                event = self.events.get_nowait()
                kind = event[0]
                if kind == "status":
                    self._set_status(event[1])
                elif kind == "file":
                    self._set_file_status(event[1], event[2])
                elif kind == "current":
                    self.current_progress.set(max(0.0, min(1.0, event[1])))
                elif kind == "batch":
                    self.batch_progress.set(max(0.0, min(1.0, event[1])))
                elif kind == "fatal":
                    self._set_running(False)
                    self._set_status(event[1])
                    messagebox.showerror("Error", event[1])
                elif kind == "finished":
                    _, success, errors, cancelled, output = event
                    self._set_running(False)
                    word = "cancelado" if cancelled else "terminado"
                    self._set_status(f"Proceso {word}. Completados: {success}; errores: {errors}.")
                    if not cancelled:
                        messagebox.showinfo(
                            "Proceso terminado",
                            f"Completados: {success}\nErrores: {errors}\n\nResultados en:\n{output}",
                        )
        except queue.Empty:
            pass
        self.after(100, self._drain_events)

    def _set_running(self, running: bool) -> None:
        state = "disabled" if running else "normal"
        for button in self.queue_buttons + [self.output_button]:
            button.configure(state=state)
        for row in self.file_rows:
            row["checkbox"].configure(state=state)
        for switch in self.format_switches:
            switch.configure(state=state)
        self.output_entry.configure(state=state)
        for box in (self.model_box, self.language_box, self.device_box, self.compute_box):
            box.configure(state=state)
        self.start_button.configure(state="disabled" if running else "normal")
        self.cancel_button.configure(state="normal" if running else "disabled")

    def _cancel(self) -> None:
        self.cancel_event.set()
        self._set_status("Cancelando al finalizar el segmento actual…")
        self.cancel_button.configure(state="disabled")

    def _close(self) -> None:
        if self.worker and self.worker.is_alive():
            if not messagebox.askyesno("Salir", "Hay una transcripción en curso. ¿Cancelar y cerrar?"):
                return
            self.cancel_event.set()
        self.destroy()


def run() -> None:
    Audio2TextApp().mainloop()
