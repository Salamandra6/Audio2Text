from __future__ import annotations

from .drag_drop_mixin import DragDropMixin
from .editor_mixin import EditorMixin
from .model_manager_mixin import ModelManagerMixin
from .productivity_panel import ProductivityPanelMixin
from .update_mixin import UpdateMixin
from .workflow_app import Audio2TextApp as WorkflowAudio2TextApp


class Audio2TextApp(
    DragDropMixin,
    EditorMixin,
    ModelManagerMixin,
    UpdateMixin,
    ProductivityPanelMixin,
    WorkflowAudio2TextApp,
):
    """Audio2Text v0.4 con herramientas de productividad modulares."""


def run() -> None:
    Audio2TextApp().mainloop()
