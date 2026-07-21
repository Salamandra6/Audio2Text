from __future__ import annotations

from pathlib import Path

from .app import BASE, BORDER, CONTROL, MUTED, YELLOW


class DragDropMixin:
    def __init__(self) -> None:
        self._dnd_targets: list[object] = []
        self._dnd_copy_action = "copy"
        self._dnd_refuse_action = "refuse_drop"
        super().__init__()
        self.after(500, self._enable_drag_drop)

    @staticmethod
    def _widget_tree(widget):
        yield widget
        try:
            children = widget.winfo_children()
        except Exception:
            children = []
        for child in children:
            yield from DragDropMixin._widget_tree(child)

    def _enable_drag_drop(self) -> None:
        try:
            from tkinterdnd2 import COPY, DND_FILES, REFUSE_DROP, TkinterDnD

            require = getattr(TkinterDnD, "require", None)
            if require is None:
                raise RuntimeError(
                    "La versión instalada de tkinterdnd2 no incluye integración pública con CustomTkinter."
                )
            require(self)
            self._dnd_copy_action = COPY
            self._dnd_refuse_action = REFUSE_DROP

            zone = getattr(self, "drop_zone", None)
            if zone is None:
                raise RuntimeError("No se encontró la zona de recepción de archivos.")

            registered: list[object] = []
            for target in self._widget_tree(zone):
                if not hasattr(target, "drop_target_register") or not hasattr(target, "dnd_bind"):
                    continue
                target.drop_target_register(DND_FILES)
                target.dnd_bind("<<DropEnter>>", self._on_drag_enter)
                target.dnd_bind("<<DropPosition>>", self._on_drag_position)
                target.dnd_bind("<<DropLeave>>", self._on_drag_leave)
                target.dnd_bind("<<Drop>>", self._on_drop_files)
                registered.append(target)

            if not registered:
                raise RuntimeError("TkDND se cargó, pero ningún widget pudo registrarse como destino.")
            self._dnd_targets = registered
            self._set_drop_zone_ready()
            self.productivity_hint.configure(
                text="Arrastre habilitado: suelta archivos o carpetas dentro de la zona amarilla."
            )
        except Exception as exc:
            self._set_drop_zone_unavailable(exc)

    def _set_drop_zone_ready(self) -> None:
        if hasattr(self, "drop_zone"):
            self.drop_zone.configure(fg_color=BASE, border_color=BORDER)
        if hasattr(self, "drop_zone_label"):
            self.drop_zone_label.configure(
                text="⬇  ARRASTRA Y SUELTA AQUÍ ARCHIVOS O CARPETAS",
                text_color=YELLOW,
            )
        if hasattr(self, "drop_zone_help"):
            self.drop_zone_help.configure(
                text="Admite uno o varios archivos y recorre las subcarpetas.",
                text_color=MUTED,
            )

    def _set_drop_zone_unavailable(self, exc: Exception) -> None:
        detail = f"{type(exc).__name__}: {exc}"
        if hasattr(self, "drop_zone"):
            self.drop_zone.configure(fg_color=BASE, border_color=BORDER)
        if hasattr(self, "drop_zone_label"):
            self.drop_zone_label.configure(text="ARRASTRE NO DISPONIBLE", text_color=MUTED)
        if hasattr(self, "drop_zone_help"):
            self.drop_zone_help.configure(text=detail, text_color=MUTED)
        if hasattr(self, "productivity_hint"):
            self.productivity_hint.configure(
                text="El arrastre no pudo activarse. Los botones Agregar archivos y Agregar carpeta siguen disponibles."
            )

    def _on_drag_enter(self, _event) -> str:
        if getattr(self, "_running", False):
            return self._dnd_refuse_action
        self.drop_zone.configure(fg_color=CONTROL, border_color=YELLOW)
        self.drop_zone_label.configure(text="SUELTA LOS ARCHIVOS AQUÍ", text_color=YELLOW)
        self.drop_zone_help.configure(text="Windows reconoció correctamente la zona de recepción.")
        return self._dnd_copy_action

    def _on_drag_position(self, _event) -> str:
        return self._dnd_refuse_action if getattr(self, "_running", False) else self._dnd_copy_action

    def _on_drag_leave(self, _event) -> str:
        self._set_drop_zone_ready()
        return self._dnd_copy_action

    def _on_drop_files(self, event) -> str:
        self._set_drop_zone_ready()
        if getattr(self, "_running", False):
            self._set_status("Espera a que finalice el proceso antes de agregar archivos.")
            return self._dnd_refuse_action
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

        if paths:
            self._add_paths(paths)
            self._set_status(f"Se recibieron {len(paths)} archivo(s) mediante arrastre.")
        else:
            self._set_status("No se encontraron archivos válidos en lo arrastrado.")
        return self._dnd_copy_action
