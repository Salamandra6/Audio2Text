from __future__ import annotations

import customtkinter as ctk

from . import __version__
from .app import BASE, BORDER, CARD, MUTED, WHITE, YELLOW, YELLOW_HOVER
from .changelog import changes_between, format_changes, full_changelog
from .state_store import load_preferences, save_preferences


class VersionNoticeMixin:
    """Muestra una sola vez las novedades posteriores a la versión vista."""

    def __init__(self) -> None:
        super().__init__()
        self.after(900, self._show_update_notice_if_needed)

    def _show_update_notice_if_needed(self) -> None:
        preferences = load_preferences()
        last_seen = str(preferences.get("last_seen_version", "0.2.1"))
        changes = changes_between(last_seen, __version__)
        if changes:
            self._open_version_notice(format_changes(changes), remember=True)

    def _open_version_notice(self, text: str | None = None, remember: bool = False) -> None:
        if getattr(self, "_version_notice_window", None) is not None:
            try:
                if self._version_notice_window.winfo_exists():
                    self._version_notice_window.focus_force()
                    return
            except Exception:
                pass

        window = ctk.CTkToplevel(self)
        self._version_notice_window = window
        window.title(f"Novedades de Audio2Text v{__version__}")
        window.geometry("760x590")
        window.minsize(620, 430)
        window.configure(fg_color=BASE)
        window.grid_columnconfigure(0, weight=1)
        window.grid_rowconfigure(2, weight=1)
        window.transient(self)

        ctk.CTkLabel(
            window,
            text=f"Audio2Text se actualizó a v{__version__}",
            text_color=WHITE,
            anchor="w",
            font=self._font(22, True),
        ).grid(row=0, column=0, sticky="ew", padx=22, pady=(20, 3))
        ctk.CTkLabel(
            window,
            text="Estas son las mejoras incorporadas, agrupadas por versión.",
            text_color=MUTED,
            anchor="w",
            font=self._font(10),
        ).grid(row=1, column=0, sticky="ew", padx=22, pady=(0, 12))

        textbox = ctk.CTkTextbox(
            window,
            fg_color=CARD,
            text_color=WHITE,
            border_width=1,
            border_color=BORDER,
            corner_radius=16,
            wrap="word",
            font=self._font(11),
        )
        textbox.grid(row=2, column=0, sticky="nsew", padx=22, pady=(0, 12))
        textbox.insert("1.0", text or full_changelog())
        textbox.configure(state="disabled")

        footer = ctk.CTkFrame(window, fg_color="transparent")
        footer.grid(row=3, column=0, sticky="ew", padx=22, pady=(0, 20))
        footer.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            footer,
            text="Uso exclusivo de su destinatario. Prohibida su comercialización.",
            text_color=MUTED,
            anchor="w",
            font=self._font(9),
        ).grid(row=0, column=0, sticky="w")
        ctk.CTkButton(
            footer,
            text="Entendido",
            command=lambda: self._close_version_notice(window, remember),
            fg_color=YELLOW,
            hover_color=YELLOW_HOVER,
            text_color=BASE,
            corner_radius=12,
            height=40,
            font=self._font(10, True),
        ).grid(row=0, column=1, sticky="e")
        window.protocol("WM_DELETE_WINDOW", lambda: self._close_version_notice(window, remember))

    def _close_version_notice(self, window, remember: bool) -> None:
        if remember:
            preferences = load_preferences()
            preferences["last_seen_version"] = __version__
            save_preferences(preferences)
        try:
            window.destroy()
        except Exception:
            pass
