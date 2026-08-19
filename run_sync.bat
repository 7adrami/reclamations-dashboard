@echo off
cd /d "%~dp0"
:loop
.venv\Scripts\python.exe sync.py >> sync.log 2>&1
echo [%date% %time%] sync.py exited with code %errorlevel%, restarting in 5s >> sync.log
timeout /t 5 /nobreak >nul
goto loop
