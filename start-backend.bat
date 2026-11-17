@echo off
REM MindTrace backend: double-click to start (Windows). First run installs everything (2-5 min).
title MindTrace backend
cd /d "%~dp0backend"

where py >nul 2>nul && (set PY=py -3) || (set PY=python)
%PY% -c "import sys; assert sys.version_info >= (3, 10), sys.version" 2>nul
if errorlevel 1 (
  echo.
  echo  Python 3.10 or newer is needed. Install it from https://www.python.org/downloads/
  echo  and tick "Add python.exe to PATH" during install. Then run this again.
  pause
  exit /b 1
)

if not exist .venv (
  echo Creating virtual environment...
  %PY% -m venv .venv || (echo Could not create venv & pause & exit /b 1)
)
call .venv\Scripts\activate.bat

if not exist .venv\installed.flag (
  echo Installing packages, this takes a few minutes the first time...
  python -m pip install --upgrade pip >nul
  python -m pip install -r requirements.txt || (echo Package install failed & pause & exit /b 1)
  echo ok> .venv\installed.flag
)

if not exist ..\.env copy ..\.env.example ..\.env >nul

echo.
echo  ==============================================================
echo   MindTrace API: http://localhost:8000/docs
echo   Teacher login: teacher@mindtrace.demo / demo1234
echo   Students: 7A-01 / 1111 ... 7A-05 / 5555
echo   Stop with Ctrl+C
echo  ==============================================================
echo.
start "" http://localhost:8000/docs
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
pause
