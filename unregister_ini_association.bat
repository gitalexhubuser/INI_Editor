@echo off
chcp 65001 >nul
cd /d "%~dp0"
py register_ini_association.py uninstall
pause
