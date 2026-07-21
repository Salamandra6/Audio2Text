from __future__ import annotations

from .advanced_panel_mixin import AdvancedPanelMixin
from .advanced_processing_mixin import AdvancedProcessingMixin
from .cuda_fallback_notice_mixin import CudaFallbackNoticeMixin
from .productivity_app import Audio2TextApp as ProductivityAudio2TextApp
from .version_notice_mixin import VersionNoticeMixin


class Audio2TextApp(
    VersionNoticeMixin,
    CudaFallbackNoticeMixin,
    AdvancedPanelMixin,
    AdvancedProcessingMixin,
    ProductivityAudio2TextApp,
):
    """Audio2Text v0.5 con análisis avanzado opcional."""


def run() -> None:
    Audio2TextApp().mainloop()
