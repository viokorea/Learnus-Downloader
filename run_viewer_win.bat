@echo off
set "VENV_DIR=venv"
set "SCRIPT_NAME=viewer.py"

echo === LearnUs Backup Viewer ===

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

REM Install Dependencies (ensure env is correct)
pip install -r requirements.txt >nul 2>&1

echo Starting Viewer...
echo Open your browser to: http://localhost:5000

REM Run Viewer Script
python "%SCRIPT_NAME%"

pause
