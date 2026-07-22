from __future__ import annotations

import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

StatusCallback = Callable[[str], None]

NETWORK_ERROR_MARKERS = (
    "could not resolve host",
    "couldn't resolve host",
    "failed to resolve",
    "name resolution",
    "getaddrinfo",
    "network is unreachable",
    "failed to connect",
    "connection timed out",
    "connection reset",
    "temporary failure in name resolution",
)


@dataclass(slots=True)
class GitUpdateInfo:
    supported: bool
    available: bool = False
    root: Path | None = None
    current_sha: str = ""
    remote_sha: str = ""
    behind_count: int = 0
    dirty: bool = False
    diverged: bool = False
    check_failed: bool = False
    network_error: bool = False
    detail: str = ""


@dataclass(slots=True)
class GitUpdateResult:
    updated: bool
    old_sha: str = ""
    new_sha: str = ""
    dependencies_updated: bool = False
    detail: str = ""


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _hidden_process_flags() -> int:
    return int(getattr(subprocess, "CREATE_NO_WINDOW", 0))


def _run(
    command: list[str],
    cwd: Path,
    *,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=str(cwd),
        check=check,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=_hidden_process_flags(),
    )


def _git(root: Path, *arguments: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return _run(["git", *arguments], root, check=check)


def _sha(root: Path, ref: str) -> str:
    return _git(root, "rev-parse", ref).stdout.strip()


def _is_ancestor(root: Path, older: str, newer: str) -> bool:
    result = _git(root, "merge-base", "--is-ancestor", older, newer, check=False)
    return result.returncode == 0


def _exception_detail(exc: BaseException) -> str:
    pieces = [str(exc)]
    if isinstance(exc, subprocess.CalledProcessError):
        if exc.stderr:
            pieces.append(str(exc.stderr))
        if exc.stdout:
            pieces.append(str(exc.stdout))
    text = " ".join(piece.strip() for piece in pieces if piece and piece.strip())
    return " ".join(text.split())[:500]


def is_network_error_text(value: str) -> bool:
    text = value.lower()
    return any(marker in text for marker in NETWORK_ERROR_MARKERS)


def check_git_update(status: StatusCallback | None = None) -> GitUpdateInfo:
    root = project_root()
    if not (root / ".git").is_dir():
        return GitUpdateInfo(False, root=root, detail="La aplicación no fue instalada mediante Git.")
    if shutil.which("git") is None:
        return GitUpdateInfo(False, root=root, detail="Git no está disponible en PATH.")

    try:
        if status:
            status("Consultando la rama principal de Audio2Text…")
        dirty = bool(_git(root, "status", "--porcelain").stdout.strip())
        _git(root, "fetch", "--quiet", "origin", "main")
        current = _sha(root, "HEAD")
        remote = _sha(root, "origin/main")

        if current == remote:
            return GitUpdateInfo(
                True,
                available=False,
                root=root,
                current_sha=current,
                remote_sha=remote,
                dirty=dirty,
                detail="La copia local coincide con origin/main.",
            )

        local_is_ancestor = _is_ancestor(root, current, remote)
        remote_is_ancestor = _is_ancestor(root, remote, current)
        diverged = not local_is_ancestor and not remote_is_ancestor
        behind = 0
        if local_is_ancestor:
            output = _git(root, "rev-list", "--count", "HEAD..origin/main").stdout.strip()
            behind = int(output or "0")

        if remote_is_ancestor:
            detail = "La copia local contiene commits propios posteriores a origin/main."
            available = False
        elif diverged:
            detail = "La copia local y origin/main tienen historiales diferentes."
            available = False
        else:
            detail = f"Hay {behind} actualización(es) de código pendiente(s)."
            available = behind > 0

        return GitUpdateInfo(
            True,
            available=available,
            root=root,
            current_sha=current,
            remote_sha=remote,
            behind_count=behind,
            dirty=dirty,
            diverged=diverged,
            detail=detail,
        )
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        technical = _exception_detail(exc)
        network_error = is_network_error_text(technical)
        detail = (
            "No se pudo conectar con GitHub. Revisa la conexión a internet o la resolución DNS."
            if network_error
            else f"No se pudo consultar Git: {technical or type(exc).__name__}."
        )
        # La instalación sigue siendo compatible con Git. Un fallo temporal de fetch
        # no debe enviarla al comprobador alternativo de Releases ni mostrar dos errores.
        return GitUpdateInfo(
            True,
            root=root,
            check_failed=True,
            network_error=network_error,
            detail=detail,
        )


def apply_git_update(
    info: GitUpdateInfo,
    status: StatusCallback | None = None,
) -> GitUpdateResult:
    if not info.supported or info.root is None:
        raise RuntimeError(info.detail or "Esta instalación no admite actualización mediante Git.")
    if info.check_failed:
        raise RuntimeError(info.detail or "No se pudo comprobar la actualización.")
    if info.dirty:
        raise RuntimeError(
            "Hay archivos modificados localmente. Guárdalos o revierte los cambios antes de actualizar."
        )
    if info.diverged:
        raise RuntimeError("La rama local está divergida y no puede actualizarse automáticamente.")
    if not info.available:
        return GitUpdateResult(False, info.current_sha, info.remote_sha, detail="No hay cambios pendientes.")

    root = info.root
    old_sha = _sha(root, "HEAD")
    if status:
        status("Descargando e instalando el código más reciente…")
    _git(root, "pull", "--ff-only", "origin", "main")
    new_sha = _sha(root, "HEAD")

    requirements = root / "requirements.txt"
    dependencies_updated = False
    if requirements.is_file():
        if status:
            status("Sincronizando dependencias de Python…")
        _run(
            [sys.executable, "-m", "pip", "install", "--upgrade", "-r", str(requirements)],
            root,
        )
        dependencies_updated = True

    return GitUpdateResult(
        updated=old_sha != new_sha,
        old_sha=old_sha,
        new_sha=new_sha,
        dependencies_updated=dependencies_updated,
        detail="Código y dependencias actualizados. Reinicia Audio2Text para aplicar los cambios.",
    )
