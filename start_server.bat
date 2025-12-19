@echo off
pushd "%~dp0"
start "" python server.py
timeout /t 1 >nul
start "" http://localhost:8000
popd
