from __future__ import annotations

import unittest

from audio2text.changelog import changes_between, format_changes
from audio2text.exporters import TranscriptSegment, TranscriptionResult
from audio2text.speaker_diarization import SpeakerTurn, assign_person_labels
from audio2text.transcript_editor import editor_text, result_from_editor_text


class VersionFiveTests(unittest.TestCase):
    def _result(self) -> TranscriptionResult:
        return TranscriptionResult(
            source_file="entrevista.wav",
            language="es",
            language_probability=0.99,
            duration=8.0,
            segments=[
                TranscriptSegment(0.0, 3.0, "Primera intervención."),
                TranscriptSegment(3.2, 7.5, "Segunda intervención."),
            ],
        )

    def test_changelog_is_grouped_by_version(self) -> None:
        changes = changes_between("0.2.1", "0.5.0")
        text = format_changes(changes)
        self.assertIn("v0.3.0", text)
        self.assertIn("v0.4.0", text)
        self.assertIn("v0.5.0", text)
        self.assertIn("- ", text)

    def test_assigns_person_labels_by_overlap(self) -> None:
        result = assign_person_labels(
            self._result(),
            [
                SpeakerTurn(0.0, 3.1, "SPEAKER_A"),
                SpeakerTurn(3.1, 8.0, "SPEAKER_B"),
            ],
        )
        self.assertEqual(result.segments[0].speaker, "Persona 1")
        self.assertEqual(result.segments[1].speaker, "Persona 2")

    def test_editor_preserves_person_labels(self) -> None:
        result = assign_person_labels(
            self._result(),
            [
                SpeakerTurn(0.0, 3.1, "A"),
                SpeakerTurn(3.1, 8.0, "B"),
            ],
        )
        text = editor_text(result).replace("Primera intervención.", "Texto corregido.")
        edited = result_from_editor_text(result, text)
        self.assertEqual(edited.segments[0].speaker, "Persona 1")
        self.assertEqual(edited.segments[0].text, "Texto corregido.")
        self.assertEqual(edited.segments[1].speaker, "Persona 2")


if __name__ == "__main__":
    unittest.main()
