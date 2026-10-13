@echo off
title Big Brother Inc.
cd /d "%~dp0"
echo Closing any older copy of Big Brother that is still running...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8765" ^| findstr "LISTENING"') do taskkill /PID %%a /F >NUL 2>NUL
set PY=
where python >NUL 2>NUL && set PY=python
if not defined PY where py >NUL 2>NUL && set PY=py
if not defined PY goto nopython
echo Checking Big Brother has everything it needs...
%PY% -m pip install --quiet --disable-pip-version-check pypdf
%PY% server.py
pause
exit /b
:nopython
echo Python is not installed. Get it from https://www.python.org/downloads/
echo and tick "Add python.exe to PATH" during install.
pause
