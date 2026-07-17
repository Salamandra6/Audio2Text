from __future__ import annotations

import customtkinter as ctk

from .app import (
    Audio2TextApp as BaseAudio2TextApp,
    CONTROL,
    HOVER,
    MUTED,
    WHITE,
    YELLOW,
)


class Audio2TextApp(BaseAudio2TextApp):
    """Audio2Text con desplazamiento vertical para la ventana completa."""

    def _build_ui(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.main_scroll = ctk.CTkScrollableFrame(
            self,
            fg_color="transparent",
            corner_radius=0,
            scrollbar_button_color=HOVER,
            scrollbar_button_hover_color=YELLOW,
        )
        self.main_scroll.grid(row=0, column=0, sticky="nsew")
        self.main_scroll.grid_columnconfigure(0, weight=1)

        header = ctk.CTkFrame(self.main_scroll, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=28, pady=(24, 18))
        header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            header,
            text="AUDIO INTELLIGENCE",
            text_color=YELLOW,
            font=self._font(11, True),
        ).grid(row=0, column=0, sticky="w")

        ctk.CTkLabel(
            header,
            text="Audio2Text",
            text_color=WHITE,
            font=self._font(32, True),
        ).grid(row=1, column=0, sticky="w", pady=(2, 0))

        ctk.CTkLabel(
            header,
            text="Transcripción local por lotes, rápida, privada y simple.",
            text_color=MUTED,
            font=self._font(13),
        ).grid(row=2, column=0, sticky="w", pady=(3, 0))

        ctk.CTkLabel(
            header,
            text="  Procesamiento local  ",
            fg_color=CONTROL,
            text_color=WHITE,
            corner_radius=16,
            height=32,
            font=self._font(11, True),
        ).grid(row=1, column=1, rowspan=2, sticky="e")

        content = ctk.CTkFrame(self.main_scroll, fg_color="transparent")
        content.grid(row=1, column=0, sticky="nsew", padx=28, pady=(0, 28))
        content.grid_columnconfigure(0, weight=1)
        content.grid_columnconfigure(1, minsize=352)
        content.grid_rowconfigure(0, weight=1)

        self._build_queue(content)
        self._build_sidebar(content)


def run() -> None:
    Audio2TextApp().mainloop()
