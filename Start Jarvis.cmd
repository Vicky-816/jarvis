@echo off
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (
  echo Install Python 3 for Windows from python.org with the Python launcher and Tcl/Tk enabled.
  pause
  exit /b 1
)
py -3 desktop.py
if errorlevel 1 pause
