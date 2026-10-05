@echo off
rem Tarea programada de Windows "triage_capturas_semanales" (calendarios/docs/CAPTURAS.md).
rem Corre el capturador de fuentes sin historico y deja la salida en calendarios\capturas\crudo\tarea.log
cd /d "%~dp0.."
set PYTHONIOENCODING=utf-8
if not exist "calendarios\capturas\crudo" mkdir "calendarios\capturas\crudo"
".venv\Scripts\python.exe" calendarios\capturas.py >> "calendarios\capturas\crudo\tarea.log" 2>&1
