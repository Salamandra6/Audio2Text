from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

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


def find_processed(path: str | Path) -> dict | None:
    try:
        return load_history().get(file_fingerprint(path))
    except OSError:
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
