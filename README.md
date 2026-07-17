# Audio2Text

Aplicación de escritorio en Python para transcribir muchos archivos de audio o video a texto. Procesa los archivos localmente con **faster-whisper**, permite trabajar por lotes y exporta los resultados como TXT, SRT, VTT o JSON.

## Características

- Interfaz gráfica para Windows construida con Tkinter.
- Selección de varios archivos o búsqueda recursiva dentro de una carpeta.
- Cola de procesamiento con estado individual por archivo.
- Detección automática de idioma o selección manual.
- Modelos `tiny`, `base`, `small`, `medium`, `large-v3` y `turbo`.
- Uso automático de CPU o GPU NVIDIA compatible.
- Filtro de actividad de voz para omitir silencios extensos.
- Exportación a texto plano y formatos de subtítulos.
- Cancelación segura entre segmentos.
- El modelo se carga una sola vez y se reutiliza para todo el lote.
- Los audios no se envían a un servicio de transcripción en la nube.

> La primera ejecución descarga desde Internet el modelo seleccionado y lo guarda en la caché del usuario. Después puede reutilizarse sin volver a descargarlo.

## Requisitos para desarrollar

- Windows 10 u 11 de 64 bits.
- Python 3.11 de 64 bits.
- Git.
- Conexión a Internet durante la instalación y la primera descarga del modelo.

## Ejecutar desde el código fuente

Abre PowerShell o Símbolo del sistema y ejecuta:

```powershell
git clone https://github.com/Salamandra6/Audio2Text.git
cd Audio2Text
py -3.11 -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python main.py
```

También puedes hacer doble clic en `run_dev.bat`; el archivo crea el entorno virtual, instala las dependencias y abre la aplicación.

## Uso de la aplicación

1. Presiona **Agregar archivos** o **Agregar carpeta**.
2. Selecciona un modelo. Para comenzar en un computador sin GPU, usa `small`.
3. Mantén **Idioma: Automático** o selecciona el idioma conocido.
4. Deja **Dispositivo** y **Precisión** en `auto`.
5. Marca los formatos de salida que necesites.
6. Elige una carpeta de destino.
7. Presiona **Iniciar transcripción**.

Los archivos con el mismo nombre no se sobrescriben: la aplicación agrega `(2)`, `(3)`, etc.

## Elección del modelo

| Modelo | Uso recomendado |
|---|---|
| `tiny` | Pruebas rápidas y equipos modestos. Menor precisión. |
| `base` | Audios claros y velocidad prioritaria. |
| `small` | Equilibrio recomendado para comenzar en CPU. |
| `medium` | Mayor precisión, pero más consumo de memoria y tiempo. |
| `turbo` | Buena velocidad y precisión en equipos potentes. |
| `large-v3` | Máxima calidad disponible, con mayor consumo de recursos. |

Para una primera prueba usa un audio corto y el modelo `small`. Si el audio tiene ruido, vocabulario técnico o varias personas hablando, compara el resultado con `medium`, `turbo` o `large-v3`.

## Generar el ejecutable en Windows

Desde la carpeta del proyecto, ejecuta:

```powershell
build_windows.bat
```

El script:

1. Crea el entorno virtual si no existe.
2. Instala las dependencias de desarrollo.
3. Ejecuta las pruebas automáticas.
4. Compila la aplicación con PyInstaller.

El resultado queda en:

```text
dist\Audio2Text\Audio2Text.exe
```

PyInstaller genera una carpeta con el `.exe` y sus bibliotecas. Para compartirlo, comprime la carpeta completa `dist\Audio2Text`; no compartas solamente el archivo `.exe`.

## Compilar desde GitHub sin instalar Python

El repositorio incluye el flujo **Build Windows** de GitHub Actions:

1. Abre la pestaña **Actions** del repositorio.
2. Selecciona **Build Windows**.
3. Presiona **Run workflow**.
4. Cuando termine, descarga el artefacto `Audio2Text-Windows`.
5. Descomprime el ZIP y abre `Audio2Text.exe`.

Para publicar una versión descargable en **Releases**, crea y sube una etiqueta:

```powershell
git tag v0.1.0
git push origin v0.1.0
```

GitHub compilará la aplicación y adjuntará `Audio2Text-Windows.zip` al lanzamiento.

## Estructura del proyecto

```text
Audio2Text/
├── .github/workflows/build-windows.yml
├── audio2text/
│   ├── __init__.py
│   ├── app.py
│   ├── exporters.py
│   └── transcriber.py
├── tests/test_exporters.py
├── Audio2Text.spec
├── build_windows.bat
├── main.py
├── requirements.txt
├── requirements-dev.txt
└── run_dev.bat
```

## Formatos admitidos

La interfaz muestra archivos WAV, MP3, M4A, FLAC, OGG, OPUS, AAC, WMA, MP4, MKV, MOV, WEBM y M4V. La compatibilidad real depende de los decodificadores incluidos por PyAV.

## Privacidad

La transcripción ocurre en el computador. El programa no contiene código para subir los audios a un servidor. Sin embargo, durante la primera utilización se conecta a Internet para descargar el modelo de reconocimiento de voz.

## Solución de problemas

### La aplicación parece detenida al iniciar

La primera carga puede estar descargando el modelo. Prueba primero con `small` y revisa que haya conexión a Internet y espacio disponible.

### El equipo no tiene GPU NVIDIA

Deja **Dispositivo: auto**. La aplicación elegirá CPU y `int8` automáticamente.

### CUDA produce un error

Selecciona **Dispositivo: cpu** y **Precisión: int8**. La aceleración CUDA requiere controladores y bibliotecas compatibles con CTranslate2.

### Windows muestra una advertencia al abrir el ejecutable

Los ejecutables creados localmente no están firmados digitalmente. Publicar el código fuente y el flujo de compilación permite revisar cómo fue construido, pero una distribución profesional debería incorporar firma de código.

## Pruebas

```powershell
python -m unittest discover -s tests -v
```

## Licencia

MIT. Consulta el archivo `LICENSE`.
