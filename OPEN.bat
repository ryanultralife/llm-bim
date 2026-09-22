@echo off
title llm-bim pack portal
cd /d "%~dp0"

set "PY="
if exist ".venv\Scripts\python.exe" set "PY=.venv\Scripts\python.exe"
if not defined PY where py >nul 2>&1 && set "PY=py -3"
if not defined PY where python >nul 2>&1 && set "PY=python"
if not defined PY (
  echo Python not found.
  pause
  exit /b 1
)

echo.
echo  Pack portal — leave this window OPEN while browsing.
echo  MineClean index:  http://127.0.0.1:8766/mineclean_studio/index.html
echo  Portal list:      http://127.0.0.1:8766/
echo.

if "%~1"=="" (
  start "" cmd /c "timeout /t 1 /nobreak >nul & start http://127.0.0.1:8766/mineclean_studio/index.html"
  %PY% examples\open_packs.py mineclean_studio --port 8766
) else (
  start "" cmd /c "timeout /t 1 /nobreak >nul & start http://127.0.0.1:8766/%~1/index.html"
  %PY% examples\open_packs.py %*
)
pause
