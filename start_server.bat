@echo off
chcp 65001 >nul
title BabyMind 서버
cd /d "%~dp0server"

set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY where python >nul 2>nul && set "PY=python"
if not defined PY (
  echo [BabyMind] 파이썬이 없습니다. https://www.python.org/downloads/ 에서 설치할 때
  echo            "Add python.exe to PATH" 를 체크한 뒤 다시 실행하세요.
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo [BabyMind] 처음 실행: 실행 환경을 준비합니다. 1~2분 걸립니다...
  %PY% -m venv .venv || (pause & exit /b 1)
)
".venv\Scripts\python.exe" -m pip install -q --disable-pip-version-check -r requirements.txt
".venv\Scripts\python.exe" run.py
pause
