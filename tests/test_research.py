from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from audio2text.exporters import TranscriptSegment, TranscriptionResult
from audio2text.research_analysis import build_sections, main_topics
from audio2text.research_documents import export_research_result


class ResearchExportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.result = TranscriptionResult(
            source_file="entrevista.mp3",
            language="es",
            language_probability=0.98,
            duration=12.0,
            segments=[
                TranscriptSegment(0.0, 4.0, "  buenos días , iniciamos la entrevista. "),
                TranscriptSegment(4.0, 8.0, "La investigación analiza evidencia digital."),
                TranscriptSegment(8.0, 12.0, "La evidencia digital debe revisarse con cuidado."),
            ],
        )

    def test_sections_include_metadata_timestamps_summary_and_topics(self) -> None:
        sections = build_sections(
            self.result,
            {
                "mode": "literal",
                "timestamps": True,
                "metadata": True,
                "summary": True,
                "topics": True,
                "correction": True,
            },
        )
        self.assertTrue(sections["metadata"])
        self.assertTrue(sections["summary"])
        self.assertTrue(sections["topics"])
        self.assertTrue(sections["transcript"][0].startswith("[00:00:00]"))
        self.assertIn("Buenos días,", sections["transcript"][0])

    def test_topics_are_local_frequency_suggestions(self) -> None:
        topics = main_topics(self.result)
        self.assertTrue(any("evidencia" in topic for topic in topics))

    def test_export_word_pdf_and_txt(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_folder:
            outputs = export_research_result(
                self.result,
                Path(temporary_folder),
                ["docx", "pdf", "txt"],
                content_options={
                    "mode": "clean",
                    "timestamps": False,
                    "metadata": True,
                    "summary": True,
                    "topics": True,
                    "correction": True,
                },
            )
            self.assertEqual({path.suffix for path in outputs}, {".docx", ".pdf", ".txt"})
            self.assertTrue(all(path.exists() and path.stat().st_size > 0 for path in outputs))
            txt = next(path for path in outputs if path.suffix == ".txt")
            content = txt.read_text(encoding="utf-8")
            self.assertIn("METADATOS", content)
            self.assertIn("RESUMEN EXTRACTIVO", content)
            self.assertIn("TRANSCRIPCIÓN LIMPIA", content)


if __name__ == "__main__":
    unittest.main()
