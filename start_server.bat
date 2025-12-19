@echo off
setlocal
pushd "%~dp0"

if exist ".venv\Scripts\activate.bat" (
    call ".venv\Scripts\activate.bat"
) else (
    echo Hinweis: Kein virtuelles Environment .venv gefunden. Python aus dem PATH wird verwendet.
)

start "" "http://127.0.0.1:5000"
python app.py
popd
