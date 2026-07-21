from __future__ import annotations

from tkinter import messagebox


class CudaFallbackNoticeMixin:
    def _productivity_event_cuda_fallback(self, detail: str) -> None:
        if hasattr(self, "advanced_hint"):
            self.advanced_hint.configure(
                text="La GPU no pudo utilizarse. Audio2Text continuará automáticamente con CPU/int8."
            )
        messagebox.showwarning(
            "Respaldo automático en CPU",
            f"{detail}\n\nEl archivo se reintentará automáticamente; no necesitas volver a agregarlo.",
        )
