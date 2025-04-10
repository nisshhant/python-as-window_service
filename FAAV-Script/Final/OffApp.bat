@echo off
echo Setting PowerShell Execution Policy to Restricted...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Set-ExecutionPolicy Restricted -Scope CurrentUser -Force"
echo All PowerShell scripts are now blocked from running.
pause
