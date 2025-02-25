@echo off
:start

:: check that python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Python is not installed. Please visit https://www.python.org/downloads/ to download and install Python.
    echo Also make sure to check the box that says "Add Python to environment variables".
    pause
    exit /b
)

:: check that ffmpeg is installed
ffmpeg -version >nul 2>&1
if %errorlevel% neq 0 (
    echo FFmpeg is not installed. Please visit https://ffmpeg.org/download.html to download and install FFmpeg.
    pause
    exit /b
)

:: If venv not exist, create it
if not exist .venv (
    python -m venv .venv
    call .venv\Scripts\activate
    pip install -r requirements.txt
)

:: Run the script
call .venv\Scripts\activate
start pythonw.exe __main__.py
