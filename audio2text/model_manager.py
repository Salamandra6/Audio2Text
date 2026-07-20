from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from faster_whisper.utils import download_model

MODEL_NAMES = ("tiny", "base", "small", "medium", "large-v3", "turbo")
DOWNLOAD_IDS = {"turbo": "large-v3-turbo"}
MODEL_DESCRIPTIONS = {
    "tiny": "Muy rápido · menor precisión",
    "base": "Rápido · recomendado para equipos modestos",
    "small": "Equilibrado · recomendado en la mayoría de equipos",
    "medium": "Mayor precisión · requiere más memoria",
    "large-v3": "Máxima precisión · equipo potente",
    "turbo": "Alta precisión y velocidad · preferible con GPU",
}


@dataclass(slots=True)
class ModelStatus:
    name: str
    installed: bool
    path: Path | None
    size_bytes: int
    description: str


def model_cache_root() -> Path:
    root = Path.home() / ".cache" / "audio2text" / "models"
    root.mkdir(parents=True, exist_ok=True)
    return root


def managed_model_path(name: str) -> Path:
    return model_cache_root() / name


def _is_complete_model(path: Path) -> bool:
    return path.is_dir() and (path / "model.bin").is_file() and (path / "config.json").is_file()


def _directory_size(path: Path) -> int:
    total = 0
    try:
        for item in path.rglob("*"):
            if item.is_file():
                try:
                    total += item.stat().st_size
                except OSError:
                    pass
    except OSError:
        pass
    return total


def find_model_path(name: str) -> Path | None:
    direct = managed_model_path(name)
    if _is_complete_model(direct):
        return direct

    root = model_cache_root()
    aliases = [name.lower()]
    if name == "turbo":
        aliases += ["large-v3-turbo", "faster-whisper-turbo"]
    for model_file in root.rglob("model.bin"):
        folder = model_file.parent
        if not (folder / "config.json").is_file():
            continue
        candidate = str(folder).lower().replace("_", "-")
        if any(alias in candidate for alias in aliases):
            return folder
    return None


def get_model_status(name: str) -> ModelStatus:
    path = find_model_path(name)
    return ModelStatus(
        name=name,
        installed=path is not None,
        path=path,
        size_bytes=_directory_size(path) if path else 0,
        description=MODEL_DESCRIPTIONS.get(name, "Modelo Whisper"),
    )


def list_model_statuses() -> list[ModelStatus]:
    return [get_model_status(name) for name in MODEL_NAMES]


def resolve_model_source(name: str) -> str:
    path = find_model_path(name)
    return str(path) if path else name


def install_model(name: str, status_callback: Callable[[str], None] | None = None) -> Path:
    if name not in MODEL_NAMES:
        raise ValueError(f"Modelo no admitido: {name}")
    existing = find_model_path(name)
    if existing:
        return existing

    root = model_cache_root()
    if status_callback:
        status_callback(f"Descargando el modelo {name}. La duración depende de Internet…")
    result = Path(download_model(DOWNLOAD_IDS.get(name, name), cache_dir=str(root)))
    if not _is_complete_model(result):
        raise RuntimeError("La descarga terminó, pero el modelo quedó incompleto.")
    if status_callback:
        status_callback(f"Modelo {name} instalado correctamente.")
    return result


def remove_model(name: str) -> bool:
    path = find_model_path(name)
    if path is None:
        return False
    root = model_cache_root().resolve()
    resolved = path.resolve()
    if resolved == root or root not in resolved.parents:
        raise RuntimeError("La ruta del modelo no pertenece al caché administrado.")

    target = resolved
    for candidate in (resolved, *resolved.parents):
        if candidate.parent == root and (candidate.name.startswith("models--") or candidate.name == name):
            target = candidate
            break
    shutil.rmtree(target)
    return True


def format_size(size_bytes: int) -> str:
    value = float(max(0, size_bytes))
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} {unit}"
        value /= 1024
    return f"{value:.1f} GB"
