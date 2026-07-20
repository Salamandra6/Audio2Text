from __future__ import annotations

from pathlib import Path


class DragDropMixin:
    def __init__(self) -> None:
        super().__init__()
        self.after(500, self._enable_drag_drop)

    def _enable_drag_drop(self) -> None:
        try:
            from tkinterdnd2 import DND_FILES, TkinterDnD

            require = getattr(TkinterDnD, "require", None) or getattr(TkinterDnD, "_require", None)
            if require is None:
                raise RuntimeError("La biblioteca no expone TkinterDnD.require.")
            require(self)
            self.drop_target_register(DND_FILES)
            self.dnd_bind("<<Drop>>", self._on_drop_files)
            self.productivity_hint.configure(
                text="Arrastre habilitado: suelta audios, videos o carpetas en cualquier parte de la ventana."
            )
        except Exception as exc:
            self.productivity_hint.configure(
                text=f"Arrastre no disponible ({type(exc).__name__}). Los botones Agregar archivos/carpeta siguen funcionando."
            )

    def _on_drop_files(self, event) -> str:
        if getattr(self, "_running", False):
            self._set_status("Espera a que finalice el proceso antes de agregar archivos.")
            return "break"
        try:
            raw_paths = self.tk.splitlist(event.data)
        except Exception:
            raw_paths = [str(event.data)]
        paths: list[Path] = []
        for value in raw_paths:
            path = Path(str(value).strip().strip("{}\"")).expanduser()
            if path.is_dir():
                paths.extend(item for item in path.rglob("*") if item.is_file())
            elif path.is_file():
                paths.append(path)
        self._add_paths(paths)
        return "break"
