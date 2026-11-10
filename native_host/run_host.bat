@echo off
rem Prefer the py launcher in C:\Windows: the browser may start this host with a
rem PATH where the per-user python.exe cannot be found.
where py >nul 2>nul && (py -3 "%~dp0host.py" & exit /b)
python "%~dp0host.py"
