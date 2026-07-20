from __future__ import annotations

import tkinter as tk
from pathlib import Path
from typing import Callable

import customtkinter as ctk

from .app import BASE, BORDER, CARD, CONTROL, HOVER, MUTED, WHITE, YELLOW, YELLOW_HOVER
from .audio_player import AudioPlaybackController
from .research_analysis import timestamp
from .transcript_editor import editor_text, marker_start_seconds


class TranscriptionEditorWindow(ctk.CTkToplevel):
    def __init__(self, parent, results: list[tuple[object, list[Path]]], save_callback: Callable[[int, str], None]) -> None:
        super().__init__(parent)
        self.results = results
        self.save_callback = save_callback
        self.current_index = len(results) - 1
        self.player = AudioPlaybackController()
        self.title("Editor de transcripción")
        self.geometry("1040x760")
        self.minsize(780, 560)
        self.configure(fg_color=BASE)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)
        self.transient(parent)
        self.protocol("WM_DELETE_WINDOW", self._close)

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
            text="Conserva los marcadores para mantener tiempos y etiquetas de Persona.",
            text_color=MUTED, font=parent._font(9),
        ).grid(row=0, column=1, sticky="e")

        player_row = ctk.CTkFrame(
            self, fg_color=CARD, corner_radius=14, border_width=1, border_color=BORDER,
        )
        player_row.grid(row=2, column=0, sticky="ew", padx=22, pady=(0, 10))
        player_row.grid_columnconfigure(2, weight=1)
        ctk.CTkButton(
            player_row, text="▶ Reproducir desde marcador", command=self._play_from_cursor,
            fg_color=YELLOW, hover_color=YELLOW_HOVER, text_color=BASE,
            corner_radius=10, height=36, font=parent._font(9, True),
        ).grid(row=0, column=0, padx=(12, 6), pady=10)
        ctk.CTkButton(
            player_row, text="■ Detener", command=self._stop_playback,
            fg_color=CONTROL, hover_color=HOVER, text_color=WHITE,
            corner_radius=10, height=36, font=parent._font(9, True),
        ).grid(row=0, column=1, padx=6, pady=10)
        self.player_status = ctk.CTkLabel(
            player_row,
            text="Reproductor opcional: sitúa el cursor en un segmento y reproduce desde ese punto.",
            text_color=MUTED, anchor="w", font=parent._font(9),
        )
        self.player_status.grid(row=0, column=2, sticky="ew", padx=(10, 12), pady=10)

        self.textbox = ctk.CTkTextbox(
            self, fg_color=CARD, text_color=WHITE, border_width=1,
            border_color=BORDER, corner_radius=16, wrap="word", font=parent._font(11),
        )
        self.textbox.grid(row=3, column=0, sticky="nsew", padx=22, pady=(0, 12))

        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.grid(row=4, column=0, sticky="ew", padx=22, pady=(0, 20))
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
        self._stop_playback()
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
        self.player_status.configure(text="Sitúa el cursor en un marcador y presiona Reproducir.")

    def _play_from_cursor(self) -> None:
        result = self.results[self.current_index][0]
        try:
            cursor = self.textbox.index("insert")
            line_number = int(str(cursor).split(".", 1)[0])
            line = self.textbox.get(f"{line_number}.0", f"{line_number}.end")
            start = marker_start_seconds(line)
            if start is None:
                start = 0.0
            self.player.play(
                result.source_file,
                start_seconds=start,
                position_callback=lambda value: self.after(0, self._on_playback_position, value),
                finished_callback=lambda error: self.after(0, self._on_playback_finished, error),
            )
            self.player_status.configure(text=f"Iniciando en {timestamp(start)}…")
        except Exception as exc:
            from tkinter import messagebox

            messagebox.showerror("No se pudo reproducir", f"{type(exc).__name__}: {exc}")

    def _on_playback_position(self, position: float) -> None:
        if not self.winfo_exists():
            return
        result = self.results[self.current_index][0]
        active_index = 0
        active_speaker = ""
        for index, segment in enumerate(result.segments):
            if segment.start <= position <= max(segment.end, segment.start + 0.05):
                active_index = index
                active_speaker = segment.speaker or ""
                break
            if segment.start <= position:
                active_index = index
                active_speaker = segment.speaker or ""
        self.player_status.configure(
            text=f"Reproduciendo {timestamp(position)}" + (f" · {active_speaker}" if active_speaker else "")
        )
        self._highlight_line(active_index + 1)

    def _highlight_line(self, line_number: int) -> None:
        try:
            widget = self.textbox._textbox
            widget.tag_remove("playback", "1.0", "end")
            widget.tag_configure("playback", background="#154b82")
            widget.tag_add("playback", f"{line_number}.0", f"{line_number}.end")
            widget.see(f"{line_number}.0")
        except Exception:
            pass

    def _on_playback_finished(self, error: str | None) -> None:
        if not self.winfo_exists():
            return
        if error:
            self.player_status.configure(text=f"Reproducción detenida: {error}")
        else:
            self.player_status.configure(text="Reproducción finalizada.")

    def _stop_playback(self) -> None:
        self.player.stop()
        if self.winfo_exists():
            self.player_status.configure(text="Reproducción detenida.")

    def _save(self) -> None:
        self.status.configure(text="Generando documentos editados…")
        self.save_callback(self.current_index, self.textbox.get("1.0", "end-1c"))

    def set_saved(self, paths: list[Path]) -> None:
        self.status.configure(text=f"Guardado: {', '.join(path.name for path in paths)}")

    def _close(self) -> None:
        self.player.stop()
        self.destroy()
