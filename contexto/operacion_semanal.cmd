@echo off
rem Tarea programada "triage_operacion_semanal" (contexto\docs\CONTEXTO_EXTERNO.md y operacion\docs\OPERACION.md).
rem Corre "python -m operacion" SIN --extraer: los conteos del hospital ya los bajo el orquestador (06:30).
rem Antes espera, hasta 90 min, a que la corrida de hoy del orquestador termine, para no leer los parquet mientras
rem la extraccion los escribe. Si se agota la espera, sigue con lo que haya. Los argumentos pasan a operacion.
cd /d "%~dp0.."
set PYTHONIOENCODING=utf-8
if not exist "salidas\operacion" mkdir "salidas\operacion"
echo ==== %date% %time% operacion_semanal.cmd %* >> "salidas\operacion\registro.log"
".venv\Scripts\python.exe" -m contexto --esperar 90 >> "salidas\operacion\registro.log" 2>&1
".venv\Scripts\python.exe" -m operacion %* >> "salidas\operacion\registro.log" 2>&1
exit /b %ERRORLEVEL%
