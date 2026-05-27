@echo off
cd /d "%~dp0¶àÄ£ÁÄ"
set PYTHONIOENCODING=utf-8
py server.py >nul 2>&1
if errorlevel 1 python server.py >nul 2>&1
if errorlevel 1 py -3 server.py >nul 2>&1
if errorlevel 1 (
    echo Python not found. Please install Python 3.8+
    echo https://www.python.org/downloads/
)
pause
