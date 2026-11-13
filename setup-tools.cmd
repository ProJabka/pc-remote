@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup-tools.ps1" %*
if errorlevel 1 pause
