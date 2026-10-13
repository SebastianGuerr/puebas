@echo off
REM Abre el tablero del pronostico en el navegador (operacion/docs/OPERACION.md).
cd /d "%~dp0\.."
".venv\Scripts\python.exe" -m streamlit run operacion\tablero.py
