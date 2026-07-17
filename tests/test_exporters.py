from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from audio2text.exporters import (
    TranscriptSegment,
    TranscriptionResult,
    _timestamp,
    export_result,
    to_srt,
    to_vtt,
)


class ExporterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.segments = [
            TranscriptSegment(start=0.0, end=1.25, text="Hola mundo."),
            TranscriptSegment(start=61.002, end=63.5, text="Segunda línea."),
        ]

    def test_timestamp_formats(self) -> None:
        self.assertEqual(_timestamp(3661.234), "01:01:01,234")
        self.assertEqual(_timestamp(1.5, "."), "00:00:01.500")

    def test_srt_output(self) -> None:
        output = to_srt(self.segments)
        self.assertIn("1\n00:00:00,000 --> 00:00:01,250", output)
        self.assertIn("Segunda línea.", output)

    def test_vtt_output(self) -> None:
        output = to_vtt(self.segments)
        self.assertTrue(output.startswith("WEBVTT"))
        self.assertIn("00:01:01.002 --> 00:01:03.500", output)

    def test_export_all_formats_and_avoid_overwrite(self) -> None:
        result = TranscriptionResult(
            source_file="reunion.mp3",
            language="es",
            language_probability=0.99,
            duration=63.5,
            segments=self.segments,
        )
        with tempfile.TemporaryDirectory() as temporary_folder:
            output_dir = Path(temporary_folder)
            first = export_result(result, output_dir, ["txt", "srt", "vtt", "json"])
            second = export_result(result, output_dir, ["txt"])

            self.assertEqual(len(first), 4)
            self.assertEqual(second[0].name, "reunion (2).txt")
            payload = json.loads((output_dir / "reunion.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["language"], "es")
            self.assertEqual(len(payload["segments"]), 2)


if __name__ == "__main__":
    unittest.main()
