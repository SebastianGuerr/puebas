@echo off
REM Ciclo semanal del pronostico de triage (operacion/docs/OPERACION.md). Programar con schtasks.
cd /d "%~dp0\.."
if not exist salidas\operacion mkdir salidas\operacion
echo ==== %date% %time% ==== >> salidas\operacion\registro.log
".venv\Scripts\python.exe" -m operacion --extraer >> salidas\operacion\registro.log 2>&1
