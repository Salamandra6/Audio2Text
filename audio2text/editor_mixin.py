from __future__ import annotations

import threading
from pathlib import Path
from tkinter import messagebox

from .editor_window import TranscriptionEditorWindow
from .research_documents import export_research_result
from .transcript_editor import result_from_editor_text


class EditorMixin:
    def _on_result_ready(self, result, written: list[Path]) -> None:
        self._productivity_events.put(("result_ready", result, list(written)))

    def _productivity_event_result_ready(self, result, written: list[Path]) -> None:
        self._completed_results.append((result, written))
        self.editor_button.configure(state="normal")
        self.productivity_hint.configure(
            text=f"Resultado listo para editar: {Path(result.source_file).name}"
        )

    def _open_editor(self) -> None:
        if not self._completed_results:
            messagebox.showinfo("Sin resultados", "Procesa al menos un archivo antes de abrir el editor.")
            return
        if self._editor_window and self._editor_window.winfo_exists():
            self._editor_window.focus_force()
            return
        self._editor_window = TranscriptionEditorWindow(
            self, self._completed_results, self._save_editor_result
        )

    def _save_editor_result(self, index: int, text: str) -> None:
        result = self._completed_results[index][0]
        edited = result_from_editor_text(result, text)
        formats = [name for name, value in self.formats.items() if value.get()]
        if not formats:
            messagebox.showwarning("Sin formato", "Selecciona Word, PDF o TXT antes de guardar.")
            return
        content_options = {
            "mode": "clean" if self.content_mode.get() == "Limpia" else "literal",
            "timestamps": self.content_options["timestamps"].get(),
            "metadata": self.content_options["metadata"].get(),
            "summary": self.content_options["summary"].get(),
            "topics": self.content_options["topics"].get(),
            "correction": self.post_correction.get(),
        }
        output = Path(self.output_dir.get()).expanduser()

        def worker() -> None:
            try:
                written = export_research_result(edited, output, formats, content_options)
                self._productivity_events.put(("editor_saved", index, edited, written))
            except Exception as exc:
                self._productivity_events.put(("productivity_error", "Editor", exc))

        threading.Thread(target=worker, daemon=True, name="Audio2TextEditorExport").start()

    def _productivity_event_editor_saved(self, index: int, edited, written: list[Path]) -> None:
        self._completed_results[index] = (edited, list(written))
        self._record_processed(Path(edited.source_file), list(written))
        if self._editor_window and self._editor_window.winfo_exists():
            self._editor_window.results = self._completed_results
            self._editor_window.set_saved(list(written))
        messagebox.showinfo("Documentos creados", "Se guardaron nuevos documentos con la edición.")
