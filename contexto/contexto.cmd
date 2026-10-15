@echo off
rem Tarea programada "triage_contexto_diario" (contexto\docs\CONTEXTO_EXTERNO.md). La lanza contexto\oculto.vbs,
rem sin ventana. Corre el orquestador desde la raiz; los argumentos pasan tal cual (p. ej. --sin-hospital).
rem La salida del orquestador va a salidas\contexto\registro\tarea.log; la de cada paso, al log del dia.
cd /d "%~dp0.."
set PYTHONIOENCODING=utf-8
if not exist "salidas\contexto\registro" mkdir "salidas\contexto\registro"
echo ==== %date% %time% contexto.cmd %* >> "salidas\contexto\registro\tarea.log"
".venv\Scripts\python.exe" -m contexto %* >> "salidas\contexto\registro\tarea.log" 2>&1
rem 0 bien; 1 fallo un paso que usa M3s; 3 ya habia otra corrida. Llega a la tarea como "Ultimo resultado".
exit /b %ERRORLEVEL%
