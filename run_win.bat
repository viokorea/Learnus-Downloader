@echo off
set "VENV_DIR=venv"

echo === LearnUs Backup Tool Setup ===

REM Check for Python
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo Python could not be found. Please install Python.
    pause
    exit /b
)

REM Create Virtual Environment if it doesn't exist
if not exist "%VENV_DIR%" (
    echo Creating virtual environment...
    python -m venv "%VENV_DIR%"
)

REM Activate Virtual Environment
call "%VENV_DIR%\Scripts\activate.bat"

REM Install Dependencies
echo Installing dependencies...
pip install -r requirements.txt

echo Setup complete!
echo Starting Application...

REM Run Main Script
python main.py

pause
