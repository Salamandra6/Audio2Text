from __future__ import annotations

import unittest
from unittest.mock import patch

from audio2text.transcriber import AudioTranscriber


class TranscriberConfigurationTests(unittest.TestCase):
    def make_transcriber(self, profile: str, device: str):
        transcriber = AudioTranscriber.__new__(AudioTranscriber)
        transcriber.performance_profile = profile
        transcriber.device = device
        return transcriber

    def test_auto_cpu_uses_fast_decoding(self):
        transcriber = self.make_transcriber("auto", "cpu")
        options = transcriber._transcription_options(30.0)
        self.assertEqual(options["beam_size"], 1)
        self.assertEqual(options["best_of"], 1)
        self.assertFalse(options["condition_on_previous_text"])

    def test_short_audio_disables_vad(self):
        transcriber = self.make_transcriber("balanced", "cpu")
        options = transcriber._transcription_options(3.0)
        self.assertFalse(options["vad_filter"])
        self.assertIsNone(options["vad_parameters"])

    def test_accurate_profile_uses_beam_five(self):
        transcriber = self.make_transcriber("accurate", "cpu")
        options = transcriber._transcription_options(60.0)
        self.assertEqual(options["beam_size"], 5)
        self.assertTrue(options["condition_on_previous_text"])

    @patch("audio2text.transcriber.os.cpu_count", return_value=4)
    def test_cpu_threads_leave_one_core_available(self, _mock_cpu_count):
        self.assertEqual(AudioTranscriber._resolve_cpu_threads("cpu", "auto"), 3)

    @patch("audio2text.transcriber.os.cpu_count", return_value=16)
    def test_auto_thread_limit_prevents_saturation(self, _mock_cpu_count):
        self.assertEqual(AudioTranscriber._resolve_cpu_threads("cpu", "auto"), 6)

    def test_gpu_does_not_override_cpu_threads(self):
        self.assertEqual(AudioTranscriber._resolve_cpu_threads("cuda", "auto"), 0)


if __name__ == "__main__":
    unittest.main()
