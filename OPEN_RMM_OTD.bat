@echo off
REM Open RMM-OTD llm-bim gallery (build first if missing)
cd /d "%~dp0"
if not exist "examples\output\rmm_otd\gallery.html" (
  echo Building RMM-OTD pack...
  set EIGEN_ROOT=%USERPROFILE%\Eigen
  if exist "%~dp0..\Eigen" set EIGEN_ROOT=%~dp0..\Eigen
  python examples\rmm_otd_cascade.py
)
start "" "examples\output\rmm_otd\gallery.html"
exit /b 0
