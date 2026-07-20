from __future__ import annotations

from collections import OrderedDict

from packaging.version import InvalidVersion, Version

CHANGELOG: "OrderedDict[str, tuple[str, ...]]" = OrderedDict(
    (
        (
            "0.3.0",
            (
                "Exportación investigativa en Word, PDF y TXT.",
                "Transcripción literal o limpia, marcas de tiempo, metadatos, resumen y temas principales.",
                "Diagnóstico previo, configuración automática, recuperación de sesión y control de duplicados.",
                "Diccionario personalizado y corrección posterior conservadora.",
            ),
        ),
        (
            "0.4.0",
            (
                "Administrador de modelos Whisper con descarga, selección y eliminación.",
                "Arrastrar y soltar archivos o carpetas.",
                "Editor integrado para corregir y volver a exportar documentos.",
                "Búsqueda y descarga asistida de actualizaciones desde GitHub Releases.",
            ),
        ),
        (
            "0.5.0",
            (
                "Identificación opcional de participantes como Persona 1, Persona 2 y siguientes.",
                "Reproductor opcional sincronizado con los segmentos del editor.",
                "Mensaje de novedades después de actualizar, organizado por versión.",
                "Módulos avanzados aislados para conservar el rendimiento en equipos modestos.",
            ),
        ),
    )
)


def changes_between(previous_version: str | None, current_version: str) -> list[tuple[str, tuple[str, ...]]]:
    """Devuelve cambios posteriores a previous_version y hasta current_version."""
    try:
        previous = Version(previous_version or "0.2.1")
    except InvalidVersion:
        previous = Version("0.2.1")
    try:
        current = Version(current_version)
    except InvalidVersion:
        return []

    changes: list[tuple[str, tuple[str, ...]]] = []
    for version, entries in CHANGELOG.items():
        parsed = Version(version)
        if previous < parsed <= current:
            changes.append((version, entries))
    return changes


def format_changes(changes: list[tuple[str, tuple[str, ...]]]) -> str:
    blocks: list[str] = []
    for version, entries in changes:
        blocks.append(f"v{version}")
        blocks.extend(f"- {entry}" for entry in entries)
        blocks.append("")
    return "\n".join(blocks).rstrip()


def full_changelog() -> str:
    return format_changes(list(CHANGELOG.items()))
