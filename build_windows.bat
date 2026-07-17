@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Creando entorno virtual con Python 3.11...
    py -3.11 -m venv .venv
    if errorlevel 1 goto :error
)

call ".venv\Scripts\activate.bat"
python -m pip install --upgrade pip
if errorlevel 1 goto :error
pip install -r requirements-dev.txt
if errorlevel 1 goto :error

python -m unittest discover -s tests -v
if errorlevel 1 goto :error

python -m PyInstaller --noconfirm --clean Audio2Text.spec
if errorlevel 1 goto :error

echo.
echo Compilacion terminada.
echo Ejecutable: dist\Audio2Text\Audio2Text.exe
explorer "dist\Audio2Text"
goto :end

:error
echo.
echo La compilacion fallo. Revisa los mensajes anteriores.
pause

:end
endlocal
