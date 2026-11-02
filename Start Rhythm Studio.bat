@echo off
cd /d "%~dp0"
if exist "%LOCALAPPDATA%\Programs\Python\Python310\python.exe" (
    "%LOCALAPPDATA%\Programs\Python\Python310\python.exe" main.py
) else (
    py main.py
)
if errorlevel 1 pause
