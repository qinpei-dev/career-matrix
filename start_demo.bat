@echo off
setlocal
chcp 65001 >nul
title CareerMatrix - Local Docker Environment

set "project_root=%~dp0"
pushd "%project_root%" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Unable to open project directory: %project_root%
    echo.
    pause
    exit /b 1
)

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%project_root%scripts\start_demo.ps1"
set "exit_code=%ERRORLEVEL%"

popd

echo.
pause
exit /b %exit_code%
