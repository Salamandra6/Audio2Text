from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from audio2text.exporters import TranscriptSegment, TranscriptionResult
from audio2text.model_manager import find_model_path, format_size, get_model_status
from audio2text.transcript_editor import editor_text, result_from_editor_text
from audio2text.update_checker import ReleaseAsset, UpdateInfo


class ProductivityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.result = TranscriptionResult(
            source_file="entrevista.wav",
            language="es",
            language_probability=0.98,
            duration=6.0,
            segments=[
                TranscriptSegment(0.0, 2.5, "Primer segmento."),
                TranscriptSegment(2.5, 6.0, "Segundo segmento."),
            ],
        )

    def test_editor_preserves_segment_times(self) -> None:
        text = editor_text(self.result).replace("Primer segmento.", "Texto corregido.")
        edited = result_from_editor_text(self.result, text)
        self.assertEqual(edited.segments[0].text, "Texto corregido.")
        self.assertEqual(edited.segments[0].start, 0.0)
        self.assertEqual(edited.segments[1].end, 6.0)

    def test_editor_without_markers_creates_single_segment(self) -> None:
        edited = result_from_editor_text(self.result, "Texto completamente reorganizado.")
        self.assertEqual(len(edited.segments), 1)
        self.assertEqual(edited.segments[0].text, "Texto completamente reorganizado.")

    def test_model_detection_in_cache(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            snapshot = root / "models--Systran--faster-whisper-base" / "snapshots" / "abc"
            snapshot.mkdir(parents=True)
            (snapshot / "model.bin").write_bytes(b"1234")
            (snapshot / "config.json").write_text("{}", encoding="utf-8")
            with patch("audio2text.model_manager.model_cache_root", return_value=root):
                self.assertEqual(find_model_path("base"), snapshot)
                status = get_model_status("base")
                self.assertTrue(status.installed)
                self.assertGreaterEqual(status.size_bytes, 6)

    def test_large_v3_does_not_match_turbo(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            snapshot = root / "models--Systran--faster-whisper-large-v3-turbo" / "snapshots" / "abc"
            snapshot.mkdir(parents=True)
            (snapshot / "model.bin").write_bytes(b"1234")
            (snapshot / "config.json").write_text("{}", encoding="utf-8")
            with patch("audio2text.model_manager.model_cache_root", return_value=root):
                self.assertIsNone(find_model_path("large-v3"))
                self.assertEqual(find_model_path("turbo"), snapshot)

    def test_update_prefers_windows_installer(self) -> None:
        info = UpdateInfo(
            True,
            version="0.4.1",
            assets=(
                ReleaseAsset("Audio2Text-Windows.zip", "zip"),
                ReleaseAsset("Audio2Text-Setup.exe", "exe"),
            ),
        )
        self.assertEqual(info.preferred_asset().name, "Audio2Text-Setup.exe")

    def test_format_size(self) -> None:
        self.assertEqual(format_size(1024), "1.0 KB")


if __name__ == "__main__":
    unittest.main()
