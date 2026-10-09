@echo off
setlocal
cd /d "%~dp0"
if errorlevel 1 goto :error

where py >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python Launcher "py" was not found.
    echo Install Python from python.org and enable the Python Launcher.
    pause
    exit /b 1
)

echo [1/2] Installing required Python packages...
py -m pip install --upgrade customtkinter pyinstaller
if errorlevel 1 goto :error

echo.
echo [2/2] Building INI Settings Editor.exe...
py -m PyInstaller --noconfirm --clean --windowed --name "INI Settings Editor" --collect-all customtkinter ini_editor.py
if errorlevel 1 goto :error

echo.
if not exist "dist\INI Settings Editor\INI Settings Editor.exe" goto :missing_exe
echo BUILD SUCCESSFUL:
echo "%CD%\dist\INI Settings Editor\INI Settings Editor.exe"
echo.
echo Next, run register_ini_association.bat to register the editor for .ini files.
pause
exit /b 0

:missing_exe
echo ERROR: Build finished, but the EXE was not found in the expected folder.
pause
exit /b 1

:error
echo.
echo ERROR: Dependency installation or build failed. Read the messages above.
pause
exit /b 1
