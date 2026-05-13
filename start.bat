@echo off
cd /d "%~dp0"

:: Try py launcher (most reliable on Windows), then python, then python3
where py >nul 2>&1
if not errorlevel 1 ( set PYTHON=py & goto :run )

where python >nul 2>&1
if not errorlevel 1 ( set PYTHON=python & goto :run )

where python3 >nul 2>&1
if not errorlevel 1 ( set PYTHON=python3 & goto :run )

echo [ERROR] Python not found.
echo Please install Python 3.8+ from https://www.python.org/downloads/
pause
exit /b 1

:run
if not exist "launcher.py" (
    echo [ERROR] launcher.py not found in this folder.
    pause
    exit /b 1
)

%PYTHON% launcher.py
if errorlevel 1 (
    echo.
    echo [ERROR] launcher.py failed to start.
    echo Try running:  python launcher.py
    pause
)
