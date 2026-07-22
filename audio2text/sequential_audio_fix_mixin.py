from __future__ import annotations

from pathlib import Path


class SequentialAudioFixMixin:
    """Mantiene utilizable la cola al agregar audios en ejecuciones sucesivas."""

    def _recover_idle_worker(self) -> None:
        worker = getattr(self, "worker", None)
        if worker is not None and not worker.is_alive():
            self.worker = None
            self._running = False
            self.cancel_event.clear()
            self._set_running(False)

    def _add_files(self) -> None:
        self._recover_idle_worker()
        super()._add_files()

    def _add_folder(self) -> None:
        self._recover_idle_worker()
        super()._add_folder()

    def _add_paths(self, paths: list[Path]) -> None:
        previous_count = len(self.files)
        previous_statuses = list(self.file_statuses)
        super()._add_paths(paths)

        added_count = len(self.files) - previous_count
        if added_count <= 0:
            return

        # Tras una ejecución anterior, una casilla antigua puede seguir marcada.
        # Como la aplicación procesa exclusivamente las casillas marcadas, eso
        # dejaba fuera al audio recién agregado. Seleccionamos solamente los
        # archivos nuevos para que la siguiente ejecución procese lo esperado.
        previous_run_finished = any(
            state in {"Completado", "Error", "Cancelado"}
            for state in previous_statuses
        )
        old_selection_exists = any(
            variable.get() for variable in self.file_selected[:previous_count]
        )
        if previous_run_finished or old_selection_exists:
            for variable in self.file_selected[:previous_count]:
                variable.set(False)
            for variable in self.file_selected[previous_count:]:
                variable.set(True)
            self._render_file_rows()
            self._set_status(
                f"{added_count} archivo(s) nuevo(s) listo(s) para la siguiente transcripción."
            )
            if hasattr(self, "_save_session"):
                self._save_session()
