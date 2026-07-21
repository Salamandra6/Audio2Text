from __future__ import annotations

from pathlib import Path

from .app import BORDER, CONTROL, MUTED, YELLOW


class DragDropMixin:
    """Convierte la cola visible de archivos en la zona de arrastre."""

    def __init__(self) -> None:
        self._dnd_targets: list[object] = []
        self._dnd_copy_action = "copy"
        self._dnd_refuse_action = "refuse_drop"
        self._dnd_files_type = None
        self._dnd_ready = False
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

    def _render_file_rows(self) -> None:
        super()._render_file_rows()
        self._update_empty_queue_hint()
        if self._dnd_ready:
            self.after_idle(self._register_queue_drop_targets)

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
            self._dnd_files_type = DND_FILES
            self._dnd_ready = True
            self._register_queue_drop_targets()
            self._set_queue_drop_ready()
            if hasattr(self, "productivity_hint"):
                self.productivity_hint.configure(
                    text="Arrastre habilitado en la cola de archivos visible en la parte superior."
                )
        except Exception as exc:
            self._dnd_ready = False
            self._set_queue_drop_unavailable(exc)

    def _candidate_targets(self) -> list[object]:
        queue_widget = getattr(self, "file_scroll", None)
        if queue_widget is None:
            return []

        candidates = list(self._widget_tree(queue_widget))
        for attribute in ("_parent_canvas", "_parent_frame", "_scrollbar"):
            candidate = getattr(queue_widget, attribute, None)
            if candidate is not None:
                candidates.extend(self._widget_tree(candidate))

        unique: list[object] = []
        seen: set[int] = set()
        for candidate in candidates:
            marker = id(candidate)
            if marker in seen:
                continue
            seen.add(marker)
            unique.append(candidate)
        return unique

    def _register_queue_drop_targets(self) -> None:
        if not self._dnd_ready or self._dnd_files_type is None:
            return

        for target in self._dnd_targets:
            try:
                if target.winfo_exists() and hasattr(target, "drop_target_unregister"):
                    target.drop_target_unregister()
            except Exception:
                pass

        registered: list[object] = []
        for target in self._candidate_targets():
            if not hasattr(target, "drop_target_register") or not hasattr(target, "dnd_bind"):
                continue
            try:
                target.drop_target_register(self._dnd_files_type)
                target.dnd_bind("<<DropEnter>>", self._on_drag_enter)
                target.dnd_bind("<<DropPosition>>", self._on_drag_position)
                target.dnd_bind("<<DropLeave>>", self._on_drag_leave)
                target.dnd_bind("<<Drop>>", self._on_drop_files)
                registered.append(target)
            except Exception:
                continue

        if not registered:
            raise RuntimeError("La cola de archivos no pudo registrarse como destino de arrastre.")
        self._dnd_targets = registered

    def _empty_queue_label(self):
        if getattr(self, "files", None):
            return None
        queue_widget = getattr(self, "file_scroll", None)
        if queue_widget is None:
            return None
        try:
            children = queue_widget.winfo_children()
        except Exception:
            return None
        for child in children:
            if hasattr(child, "configure") and child.__class__.__name__ == "CTkLabel":
                return child
        return None

    def _update_empty_queue_hint(self) -> None:
        label = self._empty_queue_label()
        if label is None:
            return
        if self._dnd_ready:
            label.configure(
                text="⬇  ARRASTRA Y SUELTA AQUÍ\nAudios, videos o carpetas completas",
                text_color=YELLOW,
            )
        else:
            label.configure(
                text="Sin archivos todavía\nAgrega archivos con los botones superiores.",
                text_color=MUTED,
            )

    def _set_queue_drop_ready(self) -> None:
        if hasattr(self, "file_scroll"):
            self.file_scroll.configure(border_color=BORDER)
        self._update_empty_queue_hint()

    def _set_queue_drop_unavailable(self, exc: Exception) -> None:
        if hasattr(self, "file_scroll"):
            self.file_scroll.configure(border_color=BORDER)
        label = self._empty_queue_label()
        if label is not None:
            label.configure(
                text="ARRASTRE NO DISPONIBLE\nUsa Agregar archivos o Agregar carpeta.",
                text_color=MUTED,
            )
        if hasattr(self, "productivity_hint"):
            self.productivity_hint.configure(
                text=f"El arrastre no pudo activarse ({type(exc).__name__}: {exc})."
            )

    def _on_drag_enter(self, _event) -> str:
        if getattr(self, "_running", False):
            return self._dnd_refuse_action
        self.file_scroll.configure(border_color=YELLOW)
        label = self._empty_queue_label()
        if label is not None:
            label.configure(text="SUELTA LOS ARCHIVOS AQUÍ", text_color=YELLOW)
        return self._dnd_copy_action

    def _on_drag_position(self, _event) -> str:
        return self._dnd_refuse_action if getattr(self, "_running", False) else self._dnd_copy_action

    def _on_drag_leave(self, _event) -> str:
        self._set_queue_drop_ready()
        return self._dnd_copy_action

    def _on_drop_files(self, event) -> str:
        self._set_queue_drop_ready()
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
            before = len(self.files)
            self._add_paths(paths)
            added = max(0, len(self.files) - before)
            self._set_status(f"Se agregaron {added} archivo(s) mediante arrastre.")
        else:
            self._set_status("No se encontraron archivos válidos en lo arrastrado.")
        return self._dnd_copy_action
