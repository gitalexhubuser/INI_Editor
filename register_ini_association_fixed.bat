@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python Launcher "py" was not found.
    echo Install Python or use the Python executable directly.
    pause
    exit /b 1
)

if not exist "register_ini_association.py" (
    echo ERROR: register_ini_association.py was not found in this folder.
    echo Extract this BAT beside the project files.
    pause
    exit /b 1
)

if not exist "ini_editor.py" (
    echo ERROR: ini_editor.py was not found in this folder.
    pause
    exit /b 1
)

if not exist "dist\INI Settings Editor\INI Settings Editor.exe" (
    echo ERROR: The EXE has not been built yet.
    echo Run build_editor_fixed.bat first and wait for BUILD SUCCESSFUL.
    pause
    exit /b 1
)

echo Registering INI Settings Editor for the current Windows user...
py register_ini_association.py install
set "RC=%ERRORLEVEL%"
echo.
if not "%RC%"=="0" echo ERROR: Registration failed. Read the Python error above.
if "%RC%"=="0" echo Registration script completed. Now choose INI Settings Editor in Windows Default Apps if needed.
pause
exit /b %RC%
