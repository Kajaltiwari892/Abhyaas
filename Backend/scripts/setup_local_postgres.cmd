@echo off
title Abhyaas PostgreSQL Setup
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup_local_postgres.ps1"
echo.
pause

