from __future__ import annotations

from pathlib import Path

import customtkinter as ctk

from .app import (
    BASE,
    BORDER,
    CARD,
    CONTROL,
    MUTED,
    STATUS_COLORS,
    WHITE,
    YELLOW,
    YELLOW_HOVER,
)


class DragDropMixin:
    """Integra una zona estable de arrastre dentro de la cola visible."""

    def __init__(self) -> None:
        self._dnd_targets: list[object] = []
        self._dnd_copy_action = "copy"
        self._dnd_refuse_action = "refuse_drop"
        self._dnd_files_type = None
        self._dnd_ready = False
        self._queue_drop_banner = None
        self._queue_drop_label = None
        self._queue_drop_help = None
        self._queue_rows_container = None
        super().__init__()
        self.after(500, self._enable_drag_drop)

    def _ensure_queue_structure(self) -> None:
        banner_exists = False
        if self._queue_drop_banner is not None:
            try:
                banner_exists = bool(self._queue_drop_banner.winfo_exists())
            except Exception:
                banner_exists = False
        if banner_exists:
            return

        for child in self.file_scroll.winfo_children():
            child.destroy()

        self._queue_drop_banner = ctk.CTkFrame(
            self.file_scroll,
            fg_color=BASE,
            border_color=BORDER,
            border_width=2,
            corner_radius=14,
            height=68,
        )
        self._queue_drop_banner.grid(row=0, column=0, sticky="ew", padx=2, pady=(2, 12))
        self._queue_drop_banner.grid_columnconfigure(0, weight=1)
        self._queue_drop_banner.grid_propagate(False)

        self._queue_drop_label = ctk.CTkLabel(
            self._queue_drop_banner,
            text="⬇  ARRASTRA Y SUELTA AQUÍ",
            text_color=YELLOW,
            anchor="center",
            font=self._font(11, True),
        )
        self._queue_drop_label.grid(row=0, column=0, sticky="ew", padx=14, pady=(10, 0))

        self._queue_drop_help = ctk.CTkLabel(
            self._queue_drop_banner,
            text="Audios, videos o carpetas completas",
            text_color=MUTED,
            anchor="center",
            font=self._font(9),
        )
        self._queue_drop_help.grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 9))

        self._queue_rows_container = ctk.CTkFrame(self.file_scroll, fg_color="transparent")
        self._queue_rows_container.grid(row=1, column=0, sticky="ew")
        self._queue_rows_container.grid_columnconfigure(0, weight=1)

    def _render_file_rows(self) -> None:
        self._ensure_queue_structure()
        container = self._queue_rows_container
        if container is None:
            return

        for child in container.winfo_children():
            child.destroy()
        self.file_rows.clear()

        total = len(self.files)
        self.file_count_label.configure(text=f"  {total} archivo{'s' if total != 1 else ''}  ")
        self._set_queue_drop_ready()

        if not self.files:
            ctk.CTkLabel(
                container,
                text="Sin archivos todavía\nTambién puedes usar los botones Agregar archivos o Agregar carpeta.",
                text_color=MUTED,
                font=self._font(12),
                justify="center",
            ).grid(row=0, column=0, sticky="nsew", pady=58)
            return

        for index, path in enumerate(self.files):
            row = ctk.CTkFrame(
                container,
                fg_color=CARD,
                corner_radius=15,
                border_width=1,
                border_color=BORDER,
            )
            row.grid(row=index, column=0, sticky="ew", pady=(0, 9), padx=2)
            row.grid_columnconfigure(1, weight=1)

            checkbox = ctk.CTkCheckBox(
                row,
                text="",
                variable=self.file_selected[index],
                width=26,
                checkbox_width=20,
                checkbox_height=20,
                corner_radius=6,
                fg_color=YELLOW,
                hover_color=YELLOW_HOVER,
                border_color=BORDER,
                checkmark_color=BASE,
            )
            checkbox.grid(row=0, column=0, rowspan=2, padx=(14, 8), pady=14)

            ctk.CTkLabel(
                row,
                text=path.name,
                text_color=WHITE,
                anchor="w",
                font=self._font(12, True),
            ).grid(row=0, column=1, sticky="ew", pady=(12, 0))
            ctk.CTkLabel(
                row,
                text=str(path.parent),
                text_color=MUTED,
                anchor="w",
                font=self._font(9),
            ).grid(row=1, column=1, sticky="ew", pady=(0, 12))

            bg, fg = STATUS_COLORS[self.file_statuses[index]]
            badge = ctk.CTkLabel(
                row,
                text=f"  {self.file_statuses[index]}  ",
                fg_color=bg,
                text_color=fg,
                corner_radius=12,
                height=26,
                font=self._font(9, True),
            )
            badge.grid(row=0, column=2, rowspan=2, padx=14)
            self.file_rows.append({"checkbox": checkbox, "status": badge})

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
            self._register_stable_drop_targets()
            self._set_queue_drop_ready()
            if hasattr(self, "productivity_hint"):
                self.productivity_hint.configure(
                    text="Arrastre habilitado en la franja superior de la cola de archivos."
                )
        except Exception as exc:
            self._dnd_ready = False
            self._set_queue_drop_unavailable(exc)

    def _stable_candidates(self) -> list[object]:
        candidates = [
            self._queue_drop_banner,
            self._queue_drop_label,
            self._queue_drop_help,
            self._queue_rows_container,
            getattr(self, "file_scroll", None),
            getattr(getattr(self, "file_scroll", None), "_parent_canvas", None),
        ]
        unique: list[object] = []
        seen: set[int] = set()
        for candidate in candidates:
            if candidate is None or id(candidate) in seen:
                continue
            seen.add(id(candidate))
            unique.append(candidate)
        return unique

    def _register_stable_drop_targets(self) -> None:
        if not self._dnd_ready or self._dnd_files_type is None:
            return

        registered: list[object] = []
        for target in self._stable_candidates():
            if not hasattr(target, "drop_target_register") or not hasattr(target, "dnd_bind"):
                continue
            target.drop_target_register(self._dnd_files_type)
            target.dnd_bind("<<DropEnter>>", self._on_drag_enter)
            target.dnd_bind("<<DropPosition>>", self._on_drag_position)
            target.dnd_bind("<<DropLeave>>", self._on_drag_leave)
            target.dnd_bind("<<Drop>>", self._on_drop_files)
            registered.append(target)

        if not registered:
            raise RuntimeError("La franja de la cola no pudo registrarse como destino de arrastre.")
        self._dnd_targets = registered

    def _set_queue_drop_ready(self) -> None:
        if self._queue_drop_banner is None:
            return
        self._queue_drop_banner.configure(fg_color=BASE, border_color=BORDER)
        if self._queue_drop_label is not None:
            self._queue_drop_label.configure(
                text="⬇  ARRASTRA MÁS ARCHIVOS AQUÍ" if self.files else "⬇  ARRASTRA Y SUELTA AQUÍ",
                text_color=YELLOW,
            )
        if self._queue_drop_help is not None:
            self._queue_drop_help.configure(
                text="La franja permanece activa aunque ya existan archivos en la cola.",
                text_color=MUTED,
            )

    def _set_queue_drop_unavailable(self, exc: Exception) -> None:
        self._ensure_queue_structure()
        if self._queue_drop_banner is not None:
            self._queue_drop_banner.configure(fg_color=BASE, border_color=BORDER)
        if self._queue_drop_label is not None:
            self._queue_drop_label.configure(text="ARRASTRE NO DISPONIBLE", text_color=MUTED)
        if self._queue_drop_help is not None:
            self._queue_drop_help.configure(
                text="Usa Agregar archivos o Agregar carpeta.",
                text_color=MUTED,
            )
        if hasattr(self, "productivity_hint"):
            self.productivity_hint.configure(
                text=f"El arrastre no pudo activarse ({type(exc).__name__}: {exc})."
            )

    def _on_drag_enter(self, _event) -> str:
        if getattr(self, "_running", False):
            return self._dnd_refuse_action
        if self._queue_drop_banner is not None:
            self._queue_drop_banner.configure(fg_color=CONTROL, border_color=YELLOW)
        if self._queue_drop_label is not None:
            self._queue_drop_label.configure(text="SUELTA LOS ARCHIVOS AQUÍ", text_color=YELLOW)
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
