from __future__ import annotations

import queue
import threading
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

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


class Audio2TextApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Audio2Text")
        self.geometry("940x700")
        self.minsize(820, 600)

        self.files: list[Path] = []
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
        self.current_progress = tk.DoubleVar(value=0)
        self.batch_progress = tk.DoubleVar(value=0)
        self.status = tk.StringVar(value="Agrega archivos o una carpeta para comenzar.")

        self._build_ui()
        self.after(100, self._drain_events)
        self.protocol("WM_DELETE_WINDOW", self._close)

    def _build_ui(self) -> None:
        root = ttk.Frame(self, padding=14)
        root.pack(fill="both", expand=True)
        root.columnconfigure(0, weight=1)
        root.rowconfigure(2, weight=1)

        ttk.Label(root, text="Audio2Text", font=("Segoe UI", 20, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Label(root, text="Transcripción local de audio por lotes").grid(row=0, column=0, sticky="e")

        settings = ttk.LabelFrame(root, text="Configuración", padding=10)
        settings.grid(row=1, column=0, sticky="ew", pady=10)
        for col in range(8):
            settings.columnconfigure(col, weight=1 if col % 2 else 0)

        ttk.Label(settings, text="Modelo").grid(row=0, column=0, sticky="w")
        self.model_box = ttk.Combobox(
            settings, textvariable=self.model,
            values=("tiny", "base", "small", "medium", "large-v3", "turbo"),
            state="readonly", width=12,
        )
        self.model_box.grid(row=0, column=1, sticky="ew", padx=(6, 14))

        ttk.Label(settings, text="Idioma").grid(row=0, column=2, sticky="w")
        self.language_box = ttk.Combobox(
            settings, textvariable=self.language, values=tuple(LANGUAGES),
            state="readonly", width=12,
        )
        self.language_box.grid(row=0, column=3, sticky="ew", padx=(6, 14))

        ttk.Label(settings, text="Dispositivo").grid(row=0, column=4, sticky="w")
        self.device_box = ttk.Combobox(
            settings, textvariable=self.device, values=("auto", "cpu", "cuda"),
            state="readonly", width=9,
        )
        self.device_box.grid(row=0, column=5, sticky="ew", padx=(6, 14))

        ttk.Label(settings, text="Precisión").grid(row=0, column=6, sticky="w")
        self.compute_box = ttk.Combobox(
            settings, textvariable=self.compute,
            values=("auto", "int8", "float16", "float32"), state="readonly", width=10,
        )
        self.compute_box.grid(row=0, column=7, sticky="ew", padx=(6, 0))

        format_frame = ttk.Frame(settings)
        format_frame.grid(row=1, column=0, columnspan=8, sticky="w", pady=(10, 0))
        ttk.Label(format_frame, text="Exportar:").pack(side="left")
        for name, variable in self.formats.items():
            ttk.Checkbutton(format_frame, text=name.upper(), variable=variable).pack(side="left", padx=(10, 0))

        queue_frame = ttk.LabelFrame(root, text="Cola de archivos", padding=10)
        queue_frame.grid(row=2, column=0, sticky="nsew")
        queue_frame.columnconfigure(0, weight=1)
        queue_frame.rowconfigure(1, weight=1)

        buttons = ttk.Frame(queue_frame)
        buttons.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        self.queue_buttons: list[ttk.Button] = []
        for text, command in (
            ("Agregar archivos", self._add_files),
            ("Agregar carpeta", self._add_folder),
            ("Quitar seleccionados", self._remove_selected),
            ("Limpiar", self._clear),
        ):
            button = ttk.Button(buttons, text=text, command=command)
            button.pack(side="left", padx=(0, 8))
            self.queue_buttons.append(button)

        self.file_list = tk.Listbox(queue_frame, selectmode=tk.EXTENDED, font=("Consolas", 10))
        self.file_list.grid(row=1, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(queue_frame, command=self.file_list.yview)
        scroll.grid(row=1, column=1, sticky="ns")
        self.file_list.configure(yscrollcommand=scroll.set)

        destination = ttk.Frame(root)
        destination.grid(row=3, column=0, sticky="ew", pady=(10, 0))
        destination.columnconfigure(1, weight=1)
        ttk.Label(destination, text="Guardar en:").grid(row=0, column=0, padx=(0, 8))
        self.output_entry = ttk.Entry(destination, textvariable=self.output_dir)
        self.output_entry.grid(row=0, column=1, sticky="ew")
        self.output_button = ttk.Button(destination, text="Elegir carpeta", command=self._choose_output)
        self.output_button.grid(row=0, column=2, padx=(8, 0))

        progress = ttk.LabelFrame(root, text="Progreso", padding=10)
        progress.grid(row=4, column=0, sticky="ew", pady=(10, 0))
        progress.columnconfigure(1, weight=1)
        ttk.Label(progress, text="Archivo actual").grid(row=0, column=0, sticky="w", padx=(0, 8))
        ttk.Progressbar(progress, variable=self.current_progress, maximum=100).grid(row=0, column=1, sticky="ew")
        ttk.Label(progress, text="Lote completo").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=(6, 0))
        ttk.Progressbar(progress, variable=self.batch_progress, maximum=100).grid(row=1, column=1, sticky="ew", pady=(6, 0))
        ttk.Label(progress, textvariable=self.status).grid(row=2, column=0, columnspan=2, sticky="w", pady=(8, 0))

        actions = ttk.Frame(root)
        actions.grid(row=5, column=0, sticky="e", pady=(10, 0))
        self.start_button = ttk.Button(actions, text="Iniciar transcripción", command=self._start)
        self.start_button.pack(side="left")
        self.cancel_button = ttk.Button(actions, text="Cancelar", command=self._cancel, state="disabled")
        self.cancel_button.pack(side="left", padx=(8, 0))

    def _add_paths(self, paths: list[Path]) -> None:
        existing = {str(path.resolve()).lower() for path in self.files}
        for path in sorted(paths, key=lambda item: item.name.lower()):
            key = str(path.resolve()).lower()
            if key in existing or path.suffix.lower() not in AUDIO_EXTENSIONS:
                continue
            self.files.append(path)
            self.file_list.insert(tk.END, f"[Pendiente] {path}")
            existing.add(key)
        self.status.set(f"{len(self.files)} archivo(s) en la cola.")

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
        for index in reversed(self.file_list.curselection()):
            self.file_list.delete(index)
            self.files.pop(index)
        self.status.set(f"{len(self.files)} archivo(s) en la cola.")

    def _clear(self) -> None:
        self.files.clear()
        self.file_list.delete(0, tk.END)
        self.status.set("Cola vacía.")

    def _choose_output(self) -> None:
        selected = filedialog.askdirectory(title="Seleccionar carpeta de salida")
        if selected:
            self.output_dir.set(selected)

    def _set_file_status(self, index: int, state: str) -> None:
        if 0 <= index < len(self.files):
            self.file_list.delete(index)
            self.file_list.insert(index, f"[{state}] {self.files[index]}")

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
            self.events.put(("current", 0))

            def progress(value: float, preview: str) -> None:
                self.events.put(("current", value * 100))
                if preview:
                    self.events.put(("status", f"{path.name}: {preview[:100]}"))

            try:
                result = transcriber.transcribe_file(
                    path, language=options["language"],
                    progress_callback=progress, cancel_event=self.cancel_event,
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
            self.events.put(("batch", ((index + 1) / total) * 100))

        self.events.put(("finished", success, errors, self.cancel_event.is_set(), options["output"]))

    def _drain_events(self) -> None:
        try:
            while True:
                event = self.events.get_nowait()
                kind = event[0]
                if kind == "status":
                    self.status.set(event[1])
                elif kind == "file":
                    self._set_file_status(event[1], event[2])
                elif kind == "current":
                    self.current_progress.set(event[1])
                elif kind == "batch":
                    self.batch_progress.set(event[1])
                elif kind == "fatal":
                    self._set_running(False)
                    self.status.set(event[1])
                    messagebox.showerror("Error", event[1])
                elif kind == "finished":
                    _, success, errors, cancelled, output = event
                    self._set_running(False)
                    word = "cancelado" if cancelled else "terminado"
                    self.status.set(f"Proceso {word}. Completados: {success}; errores: {errors}.")
                    if not cancelled:
                        messagebox.showinfo("Proceso terminado", f"Completados: {success}\nErrores: {errors}\n\nResultados en:\n{output}")
        except queue.Empty:
            pass
        self.after(100, self._drain_events)

    def _set_running(self, running: bool) -> None:
        normal = "disabled" if running else "normal"
        combo = "disabled" if running else "readonly"
        for button in self.queue_buttons + [self.output_button]:
            button.configure(state=normal)
        self.output_entry.configure(state=normal)
        for box in (self.model_box, self.language_box, self.device_box, self.compute_box):
            box.configure(state=combo)
        self.start_button.configure(state="disabled" if running else "normal")
        self.cancel_button.configure(state="normal" if running else "disabled")

    def _cancel(self) -> None:
        self.cancel_event.set()
        self.status.set("Cancelando al finalizar el segmento actual…")
        self.cancel_button.configure(state="disabled")

    def _close(self) -> None:
        if self.worker and self.worker.is_alive():
            if not messagebox.askyesno("Salir", "Hay una transcripción en curso. ¿Cancelar y cerrar?"):
                return
            self.cancel_event.set()
        self.destroy()


def run() -> None:
    Audio2TextApp().mainloop()
