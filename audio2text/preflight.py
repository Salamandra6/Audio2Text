from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

import av
import ctranslate2


@dataclass(slots=True)
class CheckResult:
    level: str
    title: str
    detail: str


@dataclass(slots=True)
class FileProbe:
    path: Path
    duration: float | None
    audio_streams: int
    size_bytes: int


def probe_audio(path: str | Path) -> FileProbe:
    source = Path(path)
    if not source.is_file():
        raise FileNotFoundError(f"No existe el archivo: {source}")
    size = source.stat().st_size
    if size <= 0:
        raise ValueError("El archivo está vacío.")

    with av.open(str(source)) as container:
        streams = [stream for stream in container.streams if stream.type == "audio"]
        if not streams:
            raise ValueError("El archivo no contiene una pista de audio.")
        duration = None
        if container.duration is not None:
            duration = max(float(container.duration) / float(av.time_base), 0.0)
        elif streams[0].duration is not None and streams[0].time_base is not None:
            duration = max(float(streams[0].duration * streams[0].time_base), 0.0)
    return FileProbe(source, duration, len(streams), size)


def recommended_settings() -> dict[str, str]:
    cores = max(1, __import__("os").cpu_count() or 1)
    try:
        cuda = ctranslate2.get_cuda_device_count() > 0
    except Exception:
        cuda = False

    if cuda:
        return {
            "model": "small",
            "device": "cuda",
            "compute": "float16",
            "profile": "Equilibrado",
            "reason": "GPU compatible detectada: se usará CUDA con precisión float16.",
        }
    if cores <= 4:
        return {
            "model": "base",
            "device": "cpu",
            "compute": "int8",
            "profile": "Rápido",
            "reason": f"Equipo de {cores} núcleos lógicos: configuración liviana para mantener Windows responsivo.",
        }
    return {
        "model": "small" if cores >= 10 else "base",
        "device": "cpu",
        "compute": "int8",
        "profile": "Automático",
        "reason": f"Equipo de {cores} núcleos lógicos: CPU int8 con hilos limitados.",
    }


def run_preflight(files: list[Path], output_dir: Path, device: str) -> list[CheckResult]:
    results: list[CheckResult] = []

    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        test = output_dir / ".audio2text_write_test"
        test.write_text("ok", encoding="utf-8")
        test.unlink(missing_ok=True)
        free = shutil.disk_usage(output_dir).free
        if free < 512 * 1024 * 1024:
            results.append(CheckResult("warning", "Poco espacio disponible", f"Quedan aproximadamente {free / 1024**2:.0f} MB."))
        else:
            results.append(CheckResult("ok", "Carpeta de destino", "La carpeta permite escribir resultados."))
    except OSError as exc:
        results.append(CheckResult("error", "Carpeta de destino", f"No se puede escribir: {exc}"))

    if device == "cuda":
        try:
            count = ctranslate2.get_cuda_device_count()
        except Exception as exc:
            count = 0
            results.append(CheckResult("error", "GPU CUDA", f"No se pudo comprobar CUDA: {exc}"))
        if count <= 0:
            results.append(CheckResult("error", "GPU CUDA", "Se eligió CUDA, pero no se detectó una GPU compatible."))
        else:
            results.append(CheckResult("ok", "GPU CUDA", f"Se detectaron {count} dispositivo(s) CUDA."))

    for path in files:
        try:
            info = probe_audio(path)
            duration = f"{info.duration:.1f} s" if info.duration is not None else "duración desconocida"
            results.append(CheckResult("ok", path.name, f"Audio válido · {duration} · {info.size_bytes / 1024**2:.1f} MB"))
        except Exception as exc:
            results.append(CheckResult("error", path.name, f"{type(exc).__name__}: {exc}"))

    return results


def has_blocking_errors(results: list[CheckResult]) -> bool:
    return any(item.level == "error" for item in results)
