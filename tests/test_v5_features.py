from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from audio2text import state_store
from audio2text.changelog import changes_between, format_changes
from audio2text.exporters import TranscriptSegment, TranscriptionResult
from audio2text.git_updater import is_network_error_text
from audio2text.speaker_diarization import SpeakerTurn, assign_person_labels
from audio2text.stable_app import Audio2TextApp as StableAudio2TextApp
from audio2text.transcript_editor import editor_text, result_from_editor_text


class Flag:
    def __init__(self, value: bool) -> None:
        self.value = value

    def get(self) -> bool:
        return self.value


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

    def test_marked_files_limit_the_batch(self) -> None:
        fake_app = SimpleNamespace(
            files=[Path("uno.wav"), Path("dos.wav"), Path("tres.wav")],
            file_selected=[Flag(False), Flag(True), Flag(False)],
        )
        indexes = StableAudio2TextApp._selected_file_indexes(fake_app)
        self.assertEqual(indexes, [1])

        fake_app.file_selected = [Flag(False), Flag(False), Flag(False)]
        indexes = StableAudio2TextApp._selected_file_indexes(fake_app)
        self.assertEqual(indexes, [0, 1, 2])

    def test_deleted_outputs_do_not_count_as_processed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            app_dir = root / "state"
            history_file = app_dir / "processed.json"
            source = root / "audio.wav"
            destination = root / "resultados"
            destination.mkdir()
            source.write_bytes(b"audio de prueba")
            output = destination / "audio.txt"
            output.write_text("transcripción", encoding="utf-8")

            with (
                patch.object(state_store, "APP_DIR", app_dir),
                patch.object(state_store, "HISTORY_FILE", history_file),
            ):
                state_store.remember_processed(source, [output])
                self.assertIsNotNone(
                    state_store.find_processed(source, output_dir=destination, formats=["txt"])
                )

                output.unlink()
                self.assertIsNone(
                    state_store.find_processed(source, output_dir=destination, formats=["txt"])
                )

    def test_update_checker_recognizes_dns_failures(self) -> None:
        self.assertTrue(is_network_error_text("Failed to resolve api.github.com: getaddrinfo failed"))
        self.assertTrue(is_network_error_text("fatal: unable to access: Could not resolve host"))
        self.assertFalse(is_network_error_text("La rama local contiene commits propios"))


if __name__ == "__main__":
    unittest.main()
