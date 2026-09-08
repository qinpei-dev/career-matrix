@echo off
setlocal
chcp 65001 >nul
title Stop CareerMatrix

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\stop_backend.ps1"
set "exit_code=%ERRORLEVEL%"

echo.
pause
exit /b %exit_code%
