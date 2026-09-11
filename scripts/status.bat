@echo off
cd /d "%~dp0.."
docker compose ps
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0status.ps1"
