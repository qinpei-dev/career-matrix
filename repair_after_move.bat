@echo off
setlocal
chcp 65001 >nul
title Repair CareerMatrix After Moving

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\repair_after_move.ps1"
set "exit_code=%ERRORLEVEL%"

echo.
pause
exit /b %exit_code%
