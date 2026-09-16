@echo off
setlocal
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\install_native_host.ps1" "%~1"
exit /b %errorlevel%
