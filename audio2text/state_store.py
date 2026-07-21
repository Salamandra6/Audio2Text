from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

APP_DIR = Path.home() / ".audio2text"
SESSION_FILE = APP_DIR / "session.json"
HISTORY_FILE = APP_DIR / "processed.json"
PREFERENCES_FILE = APP_DIR / "preferences.json"


def _read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return default


def _write_json(path: Path, payload: Any) -> None:
    APP_DIR.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def save_session(payload: dict) -> None:
    _write_json(SESSION_FILE, payload)


def load_session() -> dict:
    value = _read_json(SESSION_FILE, {})
    return value if isinstance(value, dict) else {}


def clear_session() -> None:
    try:
        SESSION_FILE.unlink(missing_ok=True)
    except OSError:
        pass


def load_preferences() -> dict:
    value = _read_json(PREFERENCES_FILE, {})
    return value if isinstance(value, dict) else {}


def save_preferences(payload: dict) -> None:
    _write_json(PREFERENCES_FILE, payload)


def file_fingerprint(path: str | Path) -> str:
    source = Path(path)
    stat = source.stat()
    digest = hashlib.sha256()
    digest.update(str(stat.st_size).encode())
    with source.open("rb") as handle:
        digest.update(handle.read(1024 * 1024))
        if stat.st_size > 1024 * 1024:
            handle.seek(max(0, stat.st_size - 1024 * 1024))
            digest.update(handle.read(1024 * 1024))
    return digest.hexdigest()


def load_history() -> dict[str, dict]:
    value = _read_json(HISTORY_FILE, {})
    return value if isinstance(value, dict) else {}


def _requested_suffixes(formats: Iterable[str] | None) -> set[str]:
    if formats is None:
        return set()
    suffixes: set[str] = set()
    for value in formats:
        name = str(value).strip().lower().lstrip(".")
        if name:
            suffixes.add(f".{name}")
    return suffixes


def _same_folder(path: Path, folder: Path) -> bool:
    try:
        return path.parent.resolve(strict=False) == folder.resolve(strict=False)
    except OSError:
        return path.parent.absolute() == folder.absolute()


def find_processed(
    path: str | Path,
    *,
    output_dir: str | Path | None = None,
    formats: Iterable[str] | None = None,
) -> dict | None:
    """Devuelve un registro solo si sus salidas solicitadas todavía existen.

    El historial no debe bloquear una nueva transcripción cuando el usuario borró
    los documentos, cambió la carpeta de destino o solicita un formato que no fue
    generado anteriormente.
    """

    try:
        fingerprint = file_fingerprint(path)
    except OSError:
        return None

    history = load_history()
    entry = history.get(fingerprint)
    if not isinstance(entry, dict):
        return None

    raw_outputs = entry.get("outputs", [])
    outputs = [Path(value).expanduser() for value in raw_outputs if isinstance(value, str) and value]
    existing = [output for output in outputs if output.is_file()]

    valid = bool(outputs) and len(existing) == len(outputs)
    if valid and output_dir is not None:
        destination = Path(output_dir).expanduser()
        existing = [output for output in existing if _same_folder(output, destination)]
        valid = bool(existing)

    requested = _requested_suffixes(formats)
    if valid and requested:
        available = {output.suffix.lower() for output in existing}
        valid = requested.issubset(available)

    if valid:
        return entry

    # Elimina el dato obsoleto para no repetir falsos avisos en ejecuciones futuras.
    history.pop(fingerprint, None)
    try:
        _write_json(HISTORY_FILE, history)
    except OSError:
        pass
    return None


def remember_processed(path: str | Path, outputs: list[Path]) -> None:
    try:
        fingerprint = file_fingerprint(path)
    except OSError:
        return
    history = load_history()
    history[fingerprint] = {
        "source": str(Path(path)),
        "outputs": [str(output) for output in outputs],
    }
    _write_json(HISTORY_FILE, history)
