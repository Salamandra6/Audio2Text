from __future__ import annotations

import os
import queue
from pathlib import Path
from tkinter import messagebox

import customtkinter as ctk

from .app import BORDER, CONTROL, HOVER, MUTED, WHITE


class ProductivityPanelMixin:
    def __init__(self) -> None:
        self._productivity_events: queue.Queue[tuple] = queue.Queue()
        self._completed_results: list[tuple[object, list[Path]]] = []
        self._model_window: ctk.CTkToplevel | None = None
        self._editor_window: ctk.CTkToplevel | None = None
        self._editor_result_index = 0
        self._updating = False
        super().__init__()
        self.after(250, self._poll_productivity_events)

    def _build_ui(self) -> None:
        super()._build_ui()
        card = self._card(self.main_scroll)
        card.grid(row=5, column=0, sticky="ew", padx=28, pady=(0, 28))
        card.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            card, text="Herramientas de productividad", text_color=WHITE,
            anchor="w", font=self._font(17, True),
        ).grid(row=0, column=0, sticky="ew", padx=18, pady=(17, 0))
        self.productivity_hint = ctk.CTkLabel(
            card,
            text="Arrastra archivos o carpetas. Administra modelos, edita resultados y busca actualizaciones.",
            text_color=MUTED, anchor="w", justify="left", wraplength=1000,
            font=self._font(10),
        )
        self.productivity_hint.grid(row=1, column=0, sticky="ew", padx=18, pady=(3, 12))

        buttons = ctk.CTkFrame(card, fg_color="transparent")
        buttons.grid(row=2, column=0, sticky="ew", padx=18, pady=(0, 18))
        for column in range(4):
            buttons.grid_columnconfigure(column, weight=1)
        self.models_button = self._tool_button(buttons, "Administrar modelos", self._open_model_manager, 0)
        self.editor_button = self._tool_button(buttons, "Abrir editor", self._open_editor, 1)
        self.editor_button.configure(state="disabled")
        self.update_button = self._tool_button(buttons, "Buscar actualizaciones", self._check_updates_manual, 2)
        self.output_folder_button = self._tool_button(buttons, "Abrir resultados", self._open_output_folder, 3)

    def _tool_button(self, parent, text: str, command, column: int) -> ctk.CTkButton:
        button = ctk.CTkButton(
            parent, text=text, command=command, fg_color=CONTROL, hover_color=HOVER,
            text_color=WHITE, border_color=BORDER, border_width=1, corner_radius=12,
            height=40, font=self._font(10, True),
        )
        button.grid(
            row=0, column=column, sticky="ew",
            padx=(0 if column == 0 else 6, 0 if column == 3 else 6),
        )
        return button

    def _poll_productivity_events(self) -> None:
        try:
            while True:
                event = self._productivity_events.get_nowait()
                handler = getattr(self, f"_productivity_event_{event[0]}", None)
                if handler:
                    handler(*event[1:])
        except queue.Empty:
            pass
        self.after(250, self._poll_productivity_events)

    def _productivity_event_productivity_error(self, title: str, exc: Exception) -> None:
        self._updating = False
        if hasattr(self, "update_button"):
            self.update_button.configure(state="normal")
        messagebox.showerror(title, f"{type(exc).__name__}: {exc}")

    def _open_output_folder(self) -> None:
        folder = Path(self.output_dir.get()).expanduser()
        folder.mkdir(parents=True, exist_ok=True)
        try:
            os.startfile(folder)  # type: ignore[attr-defined]
        except OSError as exc:
            messagebox.showerror("No se pudo abrir la carpeta", str(exc))

    def _set_running(self, running: bool) -> None:
        super()._set_running(running)
        state = "disabled" if running else "normal"
        for widget in (getattr(self, "models_button", None), getattr(self, "update_button", None)):
            if widget is not None:
                widget.configure(state=state)
        if hasattr(self, "editor_button"):
            self.editor_button.configure(
                state="normal" if not running and self._completed_results else "disabled"
            )
