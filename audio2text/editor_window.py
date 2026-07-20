from __future__ import annotations

import tkinter as tk
from pathlib import Path
from typing import Callable

import customtkinter as ctk

from .app import BASE, BORDER, CARD, CONTROL, HOVER, MUTED, WHITE, YELLOW, YELLOW_HOVER
from .transcript_editor import editor_text


class TranscriptionEditorWindow(ctk.CTkToplevel):
    def __init__(self, parent, results: list[tuple[object, list[Path]]], save_callback: Callable[[int, str], None]) -> None:
        super().__init__(parent)
        self.results = results
        self.save_callback = save_callback
        self.current_index = len(results) - 1
        self.title("Editor de transcripción")
        self.geometry("980x700")
        self.minsize(760, 520)
        self.configure(fg_color=BASE)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)
        self.transient(parent)

        ctk.CTkLabel(
            self, text="Editor de transcripción", text_color=WHITE,
            anchor="w", font=parent._font(21, True),
        ).grid(row=0, column=0, sticky="ew", padx=22, pady=(20, 4))

        selector_row = ctk.CTkFrame(self, fg_color="transparent")
        selector_row.grid(row=1, column=0, sticky="ew", padx=22, pady=(0, 10))
        selector_row.grid_columnconfigure(0, weight=1)
        names = [Path(item[0].source_file).name for item in results]
        self.selection = tk.StringVar(value=names[-1])
        self.selector = ctk.CTkOptionMenu(
            selector_row, variable=self.selection, values=names,
            command=self._select_result, fg_color=CONTROL,
            button_color=HOVER, button_hover_color=YELLOW,
            dropdown_fg_color=CONTROL, dropdown_hover_color=HOVER,
            text_color=WHITE, corner_radius=12, height=38, font=parent._font(10),
        )
        self.selector.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        ctk.CTkLabel(
            selector_row,
            text="Conserva los marcadores [#0001 00:00:00] para mantener los tiempos.",
            text_color=MUTED, font=parent._font(9),
        ).grid(row=0, column=1, sticky="e")

        self.textbox = ctk.CTkTextbox(
            self, fg_color=CARD, text_color=WHITE, border_width=1,
            border_color=BORDER, corner_radius=16, wrap="word", font=parent._font(11),
        )
        self.textbox.grid(row=2, column=0, sticky="nsew", padx=22, pady=(0, 12))

        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.grid(row=3, column=0, sticky="ew", padx=22, pady=(0, 20))
        footer.grid_columnconfigure(0, weight=1)
        self.status = ctk.CTkLabel(
            footer, text="Edita el texto y vuelve a generar los documentos.",
            text_color=MUTED, anchor="w", font=parent._font(9),
        )
        self.status.grid(row=0, column=0, sticky="ew")
        ctk.CTkButton(
            footer, text="Guardar como nuevos documentos",
            command=self._save, fg_color=YELLOW,
            hover_color=YELLOW_HOVER, text_color=BASE,
            corner_radius=12, height=40, font=parent._font(10, True),
        ).grid(row=0, column=1, padx=(10, 0))
        self.load_result(self.current_index)

    def _select_result(self, name: str) -> None:
        for index, (result, _) in enumerate(self.results):
            if Path(result.source_file).name == name:
                self.current_index = index
                self.load_result(index)
                return

    def load_result(self, index: int) -> None:
        result = self.results[index][0]
        self.textbox.configure(state="normal")
        self.textbox.delete("1.0", "end")
        self.textbox.insert("1.0", editor_text(result))
        self.status.configure(text=f"Editando: {Path(result.source_file).name}")

    def _save(self) -> None:
        self.status.configure(text="Generando documentos editados…")
        self.save_callback(self.current_index, self.textbox.get("1.0", "end-1c"))

    def set_saved(self, paths: list[Path]) -> None:
        self.status.configure(text=f"Guardado: {', '.join(path.name for path in paths)}")
