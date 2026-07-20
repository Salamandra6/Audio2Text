from __future__ import annotations

import os
import threading
from pathlib import Path
from tkinter import messagebox

from . import __version__
from .update_checker import UpdateInfo, check_for_update
from .updater import download_release_asset


class UpdateMixin:
    def _check_updates_async(self) -> None:
        def worker() -> None:
            try:
                info = check_for_update(__version__)
                if info.available:
                    self._productivity_events.put(("update_info", info, False))
            except Exception:
                pass
        threading.Thread(target=worker, daemon=True, name="Audio2TextUpdateCheck").start()

    def _check_updates_manual(self) -> None:
        self.productivity_hint.configure(text="Buscando actualizaciones…")

        def worker() -> None:
            try:
                info = check_for_update(__version__)
                self._productivity_events.put(("update_info", info, True))
            except Exception as exc:
                self._productivity_events.put(("productivity_error", "Actualización", exc))
        threading.Thread(target=worker, daemon=True, name="Audio2TextManualUpdate").start()

    def _productivity_event_update_info(self, info: UpdateInfo, manual: bool) -> None:
        if not info.available:
            self.productivity_hint.configure(text=f"Audio2Text v{__version__} está actualizado.")
            if manual:
                messagebox.showinfo("Sin actualizaciones", f"Ya tienes la versión más reciente: v{__version__}.")
            return

        notes = info.notes.strip()[:700]
        message = f"Está disponible Audio2Text v{info.version}."
        if notes:
            message += f"\n\nCambios:\n{notes}"
        asset = info.preferred_asset()
        if asset:
            message += f"\n\n¿Descargar {asset.name}?"
            if messagebox.askyesno("Actualización disponible", message):
                self._download_packaged_update(asset.url, asset.name)
        elif manual:
            messagebox.showinfo(
                "Actualización disponible",
                message + f"\n\nTodavía no existe un instalador descargable. Página:\n{info.page_url}",
            )

    def _download_packaged_update(self, url: str, name: str) -> None:
        if self._updating:
            return
        self._updating = True
        self.update_button.configure(state="disabled")

        def worker() -> None:
            try:
                path = download_release_asset(
                    url,
                    name,
                    progress=lambda value: self._productivity_events.put(("update_progress", value)),
                    status=lambda text: self._productivity_events.put(("update_status", text)),
                )
                self._productivity_events.put(("update_complete", str(path)))
            except Exception as exc:
                self._productivity_events.put(("productivity_error", "Descarga de actualización", exc))
        threading.Thread(target=worker, daemon=True, name="Audio2TextReleaseDownloader").start()

    def _productivity_event_update_status(self, text: str) -> None:
        self.productivity_hint.configure(text=text)

    def _productivity_event_update_progress(self, value: float) -> None:
        self.productivity_hint.configure(text=f"Descargando actualización: {round(value * 100)}%")

    def _productivity_event_update_complete(self, filename: str) -> None:
        self._updating = False
        self.update_button.configure(state="normal")
        path = Path(filename)
        self.productivity_hint.configure(text=f"Actualización descargada: {path}")
        if messagebox.askyesno(
            "Descarga terminada",
            f"Archivo descargado en:\n{path}\n\n¿Abrir la carpeta?",
        ):
            os.startfile(path.parent)  # type: ignore[attr-defined]
