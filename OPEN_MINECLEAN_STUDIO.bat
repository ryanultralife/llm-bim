@echo off
title MineClean studio server - KEEP OPEN
cd /d "C:\Users\ryanv\llm-bim\examples\output\mineclean_studio"
echo.
echo  MineClean studio
echo  http://127.0.0.1:18100/index.html
echo  Leave this window open.
echo.
start "" http://127.0.0.1:18100/index.html
"C:\Users\ryanv\llm-bim\.venv\Scripts\python.exe" -m http.server 18100 --bind 127.0.0.1
pause
