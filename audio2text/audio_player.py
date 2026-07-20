from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Callable

import av
import numpy as np

PositionCallback = Callable[[float], None]
FinishedCallback = Callable[[str | None], None]


class AudioPlaybackController:
    """Reproduce audio por bloques usando PyAV y sounddevice."""

    def __init__(self) -> None:
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    @staticmethod
    def available() -> tuple[bool, str]:
        try:
            import sounddevice  # noqa: F401
        except Exception as exc:
            return False, f"Reproductor no disponible: {type(exc).__name__}: {exc}"
        return True, "Reproductor disponible."

    def play(
        self,
        source: str | Path,
        start_seconds: float = 0.0,
        position_callback: PositionCallback | None = None,
        finished_callback: FinishedCallback | None = None,
    ) -> None:
        available, detail = self.available()
        if not available:
            raise RuntimeError(detail)
        self.stop()
        self._stop_event = threading.Event()
        self._thread = threading.Thread(
            target=self._worker,
            args=(Path(source), max(0.0, float(start_seconds)), position_callback, finished_callback),
            daemon=True,
            name="Audio2TextPlayback",
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()

    def _worker(
        self,
        source: Path,
        start_seconds: float,
        position_callback: PositionCallback | None,
        finished_callback: FinishedCallback | None,
    ) -> None:
        error: str | None = None
        try:
            import sounddevice as sd

            if not source.is_file():
                raise FileNotFoundError(f"No existe el audio: {source}")
            sample_rate = 44_100
            channels = 2
            with av.open(str(source)) as container:
                audio_stream = next((stream for stream in container.streams if stream.type == "audio"), None)
                if audio_stream is None:
                    raise RuntimeError("El archivo no contiene una pista de audio.")
                if start_seconds > 0:
                    container.seek(int(start_seconds * av.time_base), any_frame=False, backward=True)
                resampler = av.AudioResampler(format="flt", layout="stereo", rate=sample_rate)
                played_samples = 0
                last_report = 0.0
                with sd.OutputStream(samplerate=sample_rate, channels=channels, dtype="float32") as output:
                    for frame in container.decode(audio=audio_stream.index):
                        if self._stop_event.is_set():
                            break
                        frame_time = float(frame.pts * frame.time_base) if frame.pts is not None else 0.0
                        converted_frames = resampler.resample(frame)
                        if not isinstance(converted_frames, list):
                            converted_frames = [converted_frames]
                        for converted in converted_frames:
                            if converted is None or self._stop_event.is_set():
                                break
                            data = converted.to_ndarray()
                            if data.ndim == 1:
                                data = data.reshape(1, -1)
                            data = np.ascontiguousarray(data.T, dtype=np.float32)
                            if frame_time < start_seconds:
                                trim = min(len(data), max(0, round((start_seconds - frame_time) * sample_rate)))
                                data = data[trim:]
                            if not len(data):
                                continue
                            output.write(data)
                            played_samples += len(data)
                            now = time.monotonic()
                            if position_callback and now - last_report >= 0.18:
                                position_callback(start_seconds + played_samples / sample_rate)
                                last_report = now
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
        finally:
            if finished_callback:
                finished_callback(error)
