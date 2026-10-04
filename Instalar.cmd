@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoLogo -NoProfile -STA -ExecutionPolicy Bypass -File "%~dp0Instalar.ps1"
if errorlevel 1 (
  echo.
  echo No se pudo abrir el instalador. Conserva este aviso para comunicar el problema.
  pause
)
