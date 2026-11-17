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

REM installed.flag is a copy of requirements.txt, so new packages get installed when the list changes
fc /b requirements.txt .venv\installed.flag >nul 2>nul
if errorlevel 1 (
  echo Installing packages, this takes a few minutes the first time...
  python -m pip install --upgrade pip >nul
  python -m pip install -r requirements.txt || (echo Package install failed & pause & exit /b 1)
  copy /y requirements.txt .venv\installed.flag >nul
)

if not exist ..\.env copy ..\.env.example ..\.env >nul

REM The backend also serves the website; build it once if it is missing (after frontend changes: npm run build)
if not exist ..\frontend\dist\index.html (
  where npm >nul 2>nul && (
    echo Building the website...
    pushd ..\frontend
    call npm ci
    call npm run build
    popd
  )
)

echo.
echo  ==============================================================
echo   MindTrace website: http://localhost:8000   (API docs: /docs)
echo   Teacher login: teacher@mindtrace.demo / demo1234
echo   Students: 7A-01 / 1111 ... 7A-05 / 5555
echo   Phone / other devices: cloudflared tunnel --url http://localhost:8000
echo   Stop with Ctrl+C
echo  ==============================================================
echo.
start "" http://localhost:8000
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
pause
