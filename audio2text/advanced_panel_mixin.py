from __future__ import annotations

import tkinter as tk
import webbrowser
from tkinter import messagebox

import customtkinter as ctk

from .app import BASE, BORDER, CONTROL, HOVER, MUTED, WHITE, YELLOW
from .speaker_diarization import module_status


class AdvancedPanelMixin:
    def _build_ui(self) -> None:
        super()._build_ui()
        self.speaker_enabled = tk.BooleanVar(value=False)
        self.speaker_token = tk.StringVar(value="")
        self.speaker_count = tk.StringVar(value="Automático")

        card = self._card(self.main_scroll)
        card.grid(row=6, column=0, sticky="ew", padx=28, pady=(0, 28))
        card.grid_columnconfigure(0, weight=1)
        card.grid_columnconfigure(1, minsize=280)

        ctk.CTkLabel(
            card, text="Análisis avanzado opcional", text_color=WHITE,
            anchor="w", font=self._font(17, True),
        ).grid(row=0, column=0, sticky="ew", padx=18, pady=(17, 0))
        self.advanced_hint = ctk.CTkLabel(
            card,
            text="La identificación de personas está desactivada por defecto para conservar velocidad y memoria.",
            text_color=MUTED, anchor="w", justify="left", wraplength=760,
            font=self._font(10),
        )
        self.advanced_hint.grid(row=1, column=0, sticky="ew", padx=18, pady=(3, 12))

        ctk.CTkLabel(
            card, text="Cantidad de personas", text_color=MUTED,
            anchor="w", font=self._font(10),
        ).grid(row=0, column=1, sticky="ew", padx=(8, 18), pady=(17, 3))
        self.speaker_count_box = ctk.CTkOptionMenu(
            card, variable=self.speaker_count,
            values=["Automático", "2", "3", "4", "5", "6", "7", "8"],
            fg_color=CONTROL, button_color=HOVER, button_hover_color=YELLOW,
            dropdown_fg_color=CONTROL, dropdown_hover_color=HOVER,
            dropdown_text_color=WHITE, text_color=WHITE, corner_radius=12,
            height=38, anchor="w", font=self._font(11), dropdown_font=self._font(11),
        )
        self.speaker_count_box.grid(row=1, column=1, sticky="ew", padx=(8, 18), pady=(0, 12))

        settings = ctk.CTkFrame(
            card, fg_color=BASE, corner_radius=16, border_width=1, border_color=BORDER,
        )
        settings.grid(row=2, column=0, columnspan=2, sticky="ew", padx=18, pady=(0, 12))
        settings.grid_columnconfigure(1, weight=1)
        self.speaker_switch = ctk.CTkSwitch(
            settings, text="Identificar participantes como Persona 1, Persona 2…",
            variable=self.speaker_enabled, command=self._toggle_speaker,
            onvalue=True, offvalue=False, progress_color=YELLOW,
            button_color=WHITE, button_hover_color=WHITE,
            fg_color=CONTROL, text_color=WHITE, font=self._font(10, True),
        )
        self.speaker_switch.grid(row=0, column=0, sticky="w", padx=14, pady=14)
        self.speaker_token_entry = ctk.CTkEntry(
            settings, textvariable=self.speaker_token,
            placeholder_text="Token de Hugging Face (no se guarda)", show="•",
            state="disabled", fg_color=CONTROL, border_color=BORDER,
            text_color=WHITE, corner_radius=12, height=38, font=self._font(10),
        )
        self.speaker_token_entry.grid(row=0, column=1, sticky="ew", padx=(8, 14), pady=14)

        actions = ctk.CTkFrame(card, fg_color="transparent")
        actions.grid(row=3, column=0, columnspan=2, sticky="ew", padx=18, pady=(0, 18))
        for column in range(3):
            actions.grid_columnconfigure(column, weight=1)
        self.speaker_check_button = ctk.CTkButton(
            actions, text="Comprobar módulo", command=self._check_speaker_module,
            fg_color=CONTROL, hover_color=HOVER, text_color=WHITE,
            border_color=BORDER, border_width=1, corner_radius=12,
            height=38, font=self._font(10, True),
        )
        self.speaker_check_button.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        ctk.CTkButton(
            actions, text="Condiciones del modelo", command=self._open_speaker_conditions,
            fg_color=CONTROL, hover_color=HOVER, text_color=WHITE,
            border_color=BORDER, border_width=1, corner_radius=12,
            height=38, font=self._font(10, True),
        ).grid(row=0, column=1, sticky="ew", padx=6)
        ctk.CTkButton(
            actions, text="Ver novedades", command=lambda: self._open_version_notice(),
            fg_color=CONTROL, hover_color=HOVER, text_color=WHITE,
            border_color=BORDER, border_width=1, corner_radius=12,
            height=38, font=self._font(10, True),
        ).grid(row=0, column=2, sticky="ew", padx=(6, 0))
        self.after_idle(self._toggle_speaker)

    def _toggle_speaker(self) -> None:
        enabled = self.speaker_enabled.get() and not getattr(self, "_running", False)
        state = "normal" if enabled else "disabled"
        self.speaker_token_entry.configure(state=state)
        self.speaker_count_box.configure(state=state)

    def _check_speaker_module(self) -> None:
        available, detail = module_status()
        if available:
            messagebox.showinfo("Módulo disponible", detail)
        else:
            messagebox.showwarning(
                "Módulo avanzado no disponible",
                detail + "\n\nInstala requirements-advanced.txt y acepta las condiciones del modelo comunitario.",
            )

    @staticmethod
    def _open_speaker_conditions() -> None:
        webbrowser.open("https://huggingface.co/pyannote/speaker-diarization-community-1")

    def _show_preflight(self) -> bool:
        self._set_activity("Etapa 1/6 · Comprobando archivos y carpeta de destino…", None)
        if self.speaker_enabled.get():
            available, detail = module_status()
            if not available:
                messagebox.showerror("Módulo de personas no disponible", detail)
                return False
            if not self.speaker_token.get().strip():
                messagebox.showerror(
                    "Falta token",
                    "Ingresa un token de Hugging Face o desactiva la identificación de personas.",
                )
                return False
        return super()._show_preflight()

    def _current_options(self) -> dict:
        options = super()._current_options()
        expected = None if self.speaker_count.get() == "Automático" else int(self.speaker_count.get())
        options["speaker_options"] = {
            "enabled": self.speaker_enabled.get(),
            "token": self.speaker_token.get().strip(),
            "expected_people": expected,
        }
        return options

    def _set_running(self, running: bool) -> None:
        super()._set_running(running)
        state = "disabled" if running else "normal"
        for widget in (
            getattr(self, "speaker_switch", None),
            getattr(self, "speaker_check_button", None),
        ):
            if widget is not None:
                widget.configure(state=state)
        if not running:
            self._toggle_speaker()
