@echo off
setlocal

if exist ".venv\Scripts\activate.bat" (
    call ".venv\Scripts\activate.bat"
) else (
    echo Hinweis: Kein virtuelles Environment (.venv) gefunden. Python aus dem PATH wird verwendet.
)

python app.py
