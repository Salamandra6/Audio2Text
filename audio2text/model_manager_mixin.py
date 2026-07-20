from __future__ import annotations

import gc
import threading
from tkinter import messagebox

import customtkinter as ctk

from .app import BASE, BORDER, CARD, CONTROL, HOVER, MUTED, WHITE, YELLOW, YELLOW_HOVER
from .model_manager import format_size, install_model, list_model_statuses, remove_model


class ModelManagerMixin:
    def _open_model_manager(self) -> None:
        if self._model_window and self._model_window.winfo_exists():
            self._model_window.focus_force()
            return
        window = ctk.CTkToplevel(self)
        self._model_window = window
        window.title("Administrador de modelos")
        window.geometry("820x650")
        window.minsize(680, 480)
        window.configure(fg_color=BASE)
        window.grid_columnconfigure(0, weight=1)
        window.grid_rowconfigure(2, weight=1)
        window.transient(self)

        ctk.CTkLabel(
            window, text="Administrador de modelos Whisper", text_color=WHITE,
            anchor="w", font=self._font(21, True),
        ).grid(row=0, column=0, sticky="ew", padx=22, pady=(20, 3))
        self._model_status_label = ctk.CTkLabel(
            window,
            text="Descarga solo los modelos necesarios. Cierra la aplicación antes de eliminar un modelo que esté en uso.",
            text_color=MUTED, anchor="w", justify="left", wraplength=760,
            font=self._font(9),
        )
        self._model_status_label.grid(row=1, column=0, sticky="ew", padx=22, pady=(0, 10))
        self._model_rows = ctk.CTkScrollableFrame(
            window, fg_color=CARD, corner_radius=16, border_width=1,
            border_color=BORDER, scrollbar_button_color=HOVER,
            scrollbar_button_hover_color=YELLOW,
        )
        self._model_rows.grid(row=2, column=0, sticky="nsew", padx=22, pady=(0, 20))
        self._model_rows.grid_columnconfigure(0, weight=1)
        self._refresh_model_manager()

    def _refresh_model_manager(self) -> None:
        if not self._model_window or not self._model_window.winfo_exists():
            return
        for child in self._model_rows.winfo_children():
            child.destroy()
        for row_index, status in enumerate(list_model_statuses()):
            row = ctk.CTkFrame(
                self._model_rows, fg_color=BASE, corner_radius=14,
                border_width=1, border_color=BORDER,
            )
            row.grid(
                row=row_index, column=0, sticky="ew", padx=8,
                pady=(8 if row_index == 0 else 0, 8),
            )
            row.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(
                row, text=status.name, text_color=WHITE, anchor="w",
                font=self._font(12, True),
            ).grid(row=0, column=0, sticky="w", padx=14, pady=(11, 1))
            detail = status.description
            detail += f" · Instalado ({format_size(status.size_bytes)})" if status.installed else " · No instalado"
            ctk.CTkLabel(
                row, text=detail, text_color=MUTED, anchor="w", font=self._font(9),
            ).grid(row=1, column=0, sticky="w", padx=14, pady=(0, 11))
            ctk.CTkButton(
                row, text="Usar", command=lambda name=status.name: self._use_model(name),
                fg_color=CONTROL, hover_color=HOVER, text_color=WHITE,
                corner_radius=10, width=75, height=34, font=self._font(9, True),
            ).grid(row=0, column=1, rowspan=2, padx=(5, 5))
            action_text = "Eliminar" if status.installed else "Descargar"
            action = self._delete_model if status.installed else self._download_model
            ctk.CTkButton(
                row, text=action_text,
                command=lambda name=status.name, fn=action: fn(name),
                fg_color="transparent" if status.installed else YELLOW,
                hover_color=HOVER if status.installed else YELLOW_HOVER,
                text_color=WHITE if status.installed else BASE,
                border_color=BORDER, border_width=1 if status.installed else 0,
                corner_radius=10, width=100, height=34, font=self._font(9, True),
            ).grid(row=0, column=2, rowspan=2, padx=(5, 14))

    def _use_model(self, name: str) -> None:
        self.configuration_mode.set("Manual")
        self._on_configuration_mode("Manual")
        self.model.set(name)
        if self._model_window and self._model_window.winfo_exists():
            self._model_status_label.configure(text=f"Modelo seleccionado: {name}")

    def _download_model(self, name: str) -> None:
        if getattr(self, "_running", False):
            messagebox.showwarning("Proceso activo", "Espera a que termine la transcripción.")
            return
        self._model_status_label.configure(text=f"Preparando descarga de {name}…")

        def worker() -> None:
            try:
                path = install_model(
                    name,
                    status_callback=lambda text: self._productivity_events.put(("model_status", text)),
                )
                self._productivity_events.put(("model_installed", name, path))
            except Exception as exc:
                self._productivity_events.put(("productivity_error", "Descarga del modelo", exc))

        threading.Thread(target=worker, daemon=True, name=f"Audio2TextModel-{name}").start()

    def _delete_model(self, name: str) -> None:
        if getattr(self, "_running", False):
            messagebox.showwarning("Proceso activo", "Espera a que termine la transcripción.")
            return
        if not messagebox.askyesno("Eliminar modelo", f"¿Eliminar el modelo {name} del equipo?"):
            return
        try:
            self._transcriber_cache = None
            gc.collect()
            removed = remove_model(name)
            self._model_status_label.configure(
                text=f"Modelo {name} eliminado." if removed else "El modelo ya no estaba instalado."
            )
            self._refresh_model_manager()
        except Exception as exc:
            messagebox.showerror("No se pudo eliminar", f"{type(exc).__name__}: {exc}")

    def _productivity_event_model_status(self, text: str) -> None:
        if self._model_window and self._model_window.winfo_exists():
            self._model_status_label.configure(text=text)

    def _productivity_event_model_installed(self, name: str, _path) -> None:
        self._use_model(name)
        self._refresh_model_manager()
