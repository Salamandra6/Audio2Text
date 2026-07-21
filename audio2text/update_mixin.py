from __future__ import annotations

import os
import threading
from pathlib import Path
from tkinter import messagebox

from . import __version__
from .git_updater import GitUpdateInfo, GitUpdateResult, apply_git_update, check_git_update
from .update_checker import UpdateInfo, check_for_update
from .updater import download_release_asset


class UpdateMixin:
    def _check_updates_async(self) -> None:
        self._query_updates(manual=False)

    def _check_updates_manual(self) -> None:
        if self._updating:
            return
        self.productivity_hint.configure(text="Buscando actualizaciones…")
        self._query_updates(manual=True)

    def _query_updates(self, manual: bool) -> None:
        def worker() -> None:
            git_info = check_git_update(
                status=lambda text: self._productivity_events.put(("update_status", text))
            )
            if git_info.supported:
                self._productivity_events.put(("git_update_info", git_info, manual))
                return

            try:
                info = check_for_update(__version__)
                self._productivity_events.put(("update_info", info, manual, git_info.detail))
            except Exception as exc:
                self._productivity_events.put(("productivity_error", "Actualización", exc))

        name = "Audio2TextManualUpdate" if manual else "Audio2TextUpdateCheck"
        threading.Thread(target=worker, daemon=True, name=name).start()

    def _productivity_event_git_update_info(self, info: GitUpdateInfo, manual: bool) -> None:
        if info.available:
            if info.dirty:
                self.productivity_hint.configure(text="Hay una actualización, pero existen cambios locales.")
                messagebox.showwarning(
                    "No se puede actualizar automáticamente",
                    "Hay una actualización disponible, pero esta copia contiene archivos modificados localmente.\n\n"
                    "El actualizador no los sobrescribirá. Guarda o revierte esos cambios y vuelve a intentarlo.",
                )
                return

            message = (
                f"Hay {info.behind_count} actualización(es) de código pendiente(s) en origin/main.\n\n"
                "Audio2Text descargará el código y sincronizará las dependencias de Python. "
                "Después será necesario reiniciar la aplicación.\n\n¿Actualizar ahora?"
            )
            if messagebox.askyesno("Actualización disponible", message):
                self._apply_git_update(info)
            return

        self.productivity_hint.configure(text=f"Audio2Text v{__version__}: {info.detail}")
        if manual:
            title = "Sin actualizaciones"
            if info.diverged or "commits propios" in info.detail:
                title = "Revisión manual necesaria"
            messagebox.showinfo(title, f"Versión instalada: v{__version__}\n\n{info.detail}")

    def _apply_git_update(self, info: GitUpdateInfo) -> None:
        if self._updating:
            return
        self._updating = True
        self.update_button.configure(state="disabled")
        self.productivity_hint.configure(text="Preparando la actualización mediante Git…")

        def worker() -> None:
            try:
                result = apply_git_update(
                    info,
                    status=lambda text: self._productivity_events.put(("update_status", text)),
                )
                self._productivity_events.put(("git_update_complete", result))
            except Exception as exc:
                self._productivity_events.put(("productivity_error", "Actualización mediante Git", exc))

        threading.Thread(target=worker, daemon=True, name="Audio2TextGitUpdater").start()

    def _productivity_event_git_update_complete(self, result: GitUpdateResult) -> None:
        self._updating = False
        self.update_button.configure(state="normal")
        self.productivity_hint.configure(text=result.detail)
        if not result.updated:
            messagebox.showinfo("Sin cambios", result.detail)
            return

        close_now = messagebox.askyesno(
            "Actualización instalada",
            "El código y las dependencias se actualizaron correctamente.\n\n"
            "Cierra y vuelve a abrir Audio2Text para cargar la nueva versión.\n\n"
            "¿Cerrar la aplicación ahora?",
        )
        if close_now:
            self.destroy()

    def _productivity_event_update_info(
        self,
        info: UpdateInfo,
        manual: bool,
        git_detail: str = "",
    ) -> None:
        if not info.available:
            self.productivity_hint.configure(text=f"Audio2Text v{__version__} está actualizado.")
            if manual:
                extra = f"\n\nActualización mediante Git no disponible: {git_detail}" if git_detail else ""
                messagebox.showinfo(
                    "Sin actualizaciones",
                    f"Ya tienes la versión más reciente publicada: v{__version__}.{extra}",
                )
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
