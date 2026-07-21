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
        (
            "0.5.1",
            (
                "Respaldo automático en CPU/int8 cuando CUDA, cuBLAS o cuDNN no pueden utilizarse.",
                "Reintento automático del mismo archivo sin volver a agregarlo.",
                "Eliminación del segundo aviso falso sobre un hilo terminado sin evento final.",
                "Diagnóstico más claro para instalaciones NVIDIA incompletas.",
            ),
        ),
        (
            "0.5.2",
            (
                "El botón Buscar actualizaciones ahora consulta directamente origin/main en instalaciones Git.",
                "Actualización del código y sincronización de dependencias desde la aplicación.",
                "Protección contra sobrescritura cuando existen cambios locales o ramas divergidas.",
                "Compatibilidad conservada con instaladores publicados mediante GitHub Releases.",
            ),
        ),
        (
            "0.5.3",
            (
                "Corrección del arrastre nativo de archivos en ventanas CustomTkinter.",
                "Nueva zona visible para soltar uno o varios archivos o carpetas.",
                "Indicador visual al entrar, salir y soltar sobre la zona de recepción.",
                "Actualización de TkinterDnD a la integración pública compatible con CustomTkinter.",
            ),
        ),
        (
            "0.5.4",
            (
                "La cola de archivos superior ahora funciona directamente como zona de arrastre.",
                "Se pueden agregar más archivos soltándolos encima de las filas ya cargadas.",
                "La cola vacía muestra una instrucción visible para arrastrar audios, videos o carpetas.",
                "Se eliminó la zona de arrastre inferior duplicada para reducir el desplazamiento.",
            ),
        ),
        (
            "0.5.5",
            (
                "Corrección del cierre al agregar un segundo archivo con la aplicación abierta.",
                "La zona de arrastre se registra una sola vez y ya no conserva referencias a filas destruidas.",
                "Franja de arrastre permanente dentro de la cola de archivos.",
                "La lista puede reconstruirse varias veces sin reinicializar TkDND.",
            ),
        ),
        (
            "0.5.6",
            (
                "Las casillas marcadas ahora limitan el procesamiento a esos archivos; sin marcas se procesa toda la cola.",
                "El control de duplicados revisa solo los archivos elegidos para la ejecución actual.",
                "Los resultados borrados o pertenecientes a otra carpeta dejan de bloquear una nueva transcripción.",
                "Omitir un resultado existente ya no quita ni borra archivos de la cola.",
                "Los estados de progreso permanecen asociados a la fila correcta al procesar una selección parcial.",
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
