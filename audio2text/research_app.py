from __future__ import annotations

from .stable_app import Audio2TextApp as StableAudio2TextApp


class Audio2TextApp(StableAudio2TextApp):
    pass


def run() -> None:
    Audio2TextApp().mainloop()
