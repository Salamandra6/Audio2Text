from __future__ import annotations

from pathlib import Path
from typing import Callable

import requests

StatusCallback = Callable[[str], None]
ProgressCallback = Callable[[float], None]


def download_release_asset(
    url: str,
    filename: str,
    progress: ProgressCallback | None = None,
    status: StatusCallback | None = None,
) -> Path:
    destination = Path.home() / "Downloads" / "Audio2Text_updates"
    destination.mkdir(parents=True, exist_ok=True)
    target = destination / filename
    temporary = target.with_suffix(target.suffix + ".part")
    if status:
        status(f"Descargando {filename}…")
    with requests.get(url, stream=True, timeout=(10, 60), headers={"User-Agent": "Audio2Text"}) as response:
        response.raise_for_status()
        total = int(response.headers.get("content-length", "0") or 0)
        received = 0
        with temporary.open("wb") as handle:
            for chunk in response.iter_content(chunk_size=1024 * 256):
                if not chunk:
                    continue
                handle.write(chunk)
                received += len(chunk)
                if progress and total:
                    progress(min(received / total, 1.0))
    temporary.replace(target)
    if status:
        status(f"Actualización descargada en {target}")
    return target
