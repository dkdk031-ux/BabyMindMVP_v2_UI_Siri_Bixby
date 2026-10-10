#!/usr/bin/env bash
# Mac / Linux 용 서버 실행 (처음 실행 시 자동 설치)
set -e
cd "$(dirname "$0")/server"
if [ ! -x .venv/bin/python ]; then
  echo "[BabyMind] 처음 실행: 실행 환경을 준비합니다..."
  python3 -m venv .venv
fi
.venv/bin/python -m pip install -q --disable-pip-version-check -r requirements.txt
exec .venv/bin/python run.py
