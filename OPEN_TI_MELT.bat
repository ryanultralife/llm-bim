@echo off
title Ti-Melt studio server - KEEP OPEN
cd /d "C:\Users\ryanv\llm-bim\examples\output\mb_ti_melt_studio"
echo.
echo  MB-Ti-Melt studio
echo  http://127.0.0.1:18220/index.html
echo  Leave this window open.
echo.
start "" http://127.0.0.1:18220/index.html
"C:\Users\ryanv\llm-bim\.venv\Scripts\python.exe" -m http.server 18220 --bind 127.0.0.1
pause
