@echo off
setlocal
title MineClean — index.html
cd /d "%~dp0"

set "PACK=%~dp0examples\output\mineclean_studio"
set "INDEX=%PACK%\index.html"

if not exist "%INDEX%" (
  echo.
  echo  ERROR: index.html not found:
  echo  %INDEX%
  echo.
  pause
  exit /b 1
)

echo.
echo  ============================================
echo   MineClean pack
echo  ============================================
echo.
echo  Opening index.html two ways:
echo    1. file://  (always works — no server)
echo    2. http://  (needed for full 3D studio)
echo.
echo  Pack folder:
echo  %PACK%
echo.

REM --- Always open file:// first (no server needed) ---
start "" "%INDEX%"

REM --- Try local server for 3D / iframe ---
set "PY="
if exist "%~dp0.venv\Scripts\python.exe" set "PY=%~dp0.venv\Scripts\python.exe"
if not defined PY where py >nul 2>&1 && set "PY=py -3"
if not defined PY where python >nul 2>&1 && set "PY=python"

if not defined PY (
  echo  Python not found — file:// page is open.
  echo  For 3D studio install Python or use .venv.
  echo.
  pause
  exit /b 0
)

set PORT=18080
echo  Starting server on port %PORT% ...
echo  3D link:  http://127.0.0.1:%PORT%/index.html
echo.
echo  KEEP THIS WINDOW OPEN while using 3D.
echo  Close window to stop the server.
echo.

timeout /t 1 /nobreak >nul
start "" "http://127.0.0.1:%PORT%/index.html"

cd /d "%PACK%"
"%PY%" -m http.server %PORT% --bind 127.0.0.1
echo.
echo  Server stopped.
pause
