@echo off
cd /d "%~dp0"
where node >nul 2>nul
if errorlevel 1 (
  echo Please install Node.js 20.19 or newer, then run this file again.
  pause
  exit /b 1
)
start "" http://localhost:8080
node scripts/serve-dist.mjs
pause
