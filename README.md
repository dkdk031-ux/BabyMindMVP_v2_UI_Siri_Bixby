# BabyMind (안드로이드 + 빅스비 육아기록)

> 목표: **"하이빅스비, 우리애기 11시10분에 500ml 분유 먹었어"** → 갤럭시 홈 미니가 알아듣고 → 앱에 기록

## 구조

```
 갤럭시 홈 미니 ─(Bixby 캡슐)─┐
                              ├─▶  BabyMind 서버 (FastAPI + SQLite)  ◀── 안드로이드 앱 (Flutter)
 휴대폰 앱 마이크/입력 ────────┘        POST /log  "문장 → 기록 저장"      15초마다 새로고침
```

스피커와 휴대폰은 서로 다른 기기라서 **기록은 서버 한 곳에 저장**하고, 앱은 서버에서 읽어옵니다.

| 폴더 | 내용 |
|---|---|
| `server/` | FastAPI 서버. 문장 해석(규칙 기반 + 선택적으로 OpenAI), SQLite 저장, 요약/질문 API |
| `app/` | Flutter 안드로이드 앱. 오늘 요약 / 7일 기록 / AI 질문 / 서버 설정 |
| `bixby/` | 갤럭시 홈 미니 연결 가이드 + Bixby 캡슐 초안 |
| `BabyMindMVP_v2_UI_Siri_Bixby/` | 이전 iOS(SwiftUI) 버전 — 참고용, 필요 없으면 삭제 |

## 1단계: 서버 실행 (집 PC)

```bash
cd server
python -m venv .venv
# Windows: .venv\Scripts\activate   /  Mac·Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # Windows: copy .env.example .env
uvicorn main:app --host 0.0.0.0 --port 8000
```

- 브라우저에서 `http://127.0.0.1:8000/docs` 를 열면 API를 바로 테스트할 수 있습니다.
- **OpenAI 키 없이도** 기본 문장은 규칙 기반 파서로 기록됩니다.
  `OPENAI_API_KEY`를 넣으면 "분유 먹고 응가했어"처럼 한 문장에 여러 기록이 있는 경우와 AI 질문이 더 똑똑해집니다.
- 테스트: `python -m pytest tests`

규칙 파서가 이해하는 예:

| 말 | 저장 결과 |
|---|---|
| 우리애기 11시10분에 500ml 분유 먹었어 | 분유 500ml, 11:10 (오전/오후는 지금 기준 가장 최근 시각) |
| 방금 분유 180 먹었어 | 분유 180ml, 지금 |
| 20분 전에 응가했어 | 기저귀(대변), 20분 전 |
| 밤 11시부터 6시반까지 잤어 | 수면 7시간 30분 (자정 넘김 처리) |
| 체온 37.5도 | 체온 37.5℃ |

## 2단계: 안드로이드 앱

1. [Flutter](https://docs.flutter.dev/get-started/install) + Android Studio 설치
2. ```bash
   cd app
   flutter pub get
   flutter run            # 휴대폰 USB 연결 후 (개발자 옵션 > USB 디버깅)
   flutter build apk      # 설치 파일: build/app/outputs/flutter-apk/app-release.apk
   ```
3. 앱 첫 화면의 **서버 설정**에 PC 주소 입력: `http://192.168.0.10:8000`
   (PC에서 `ipconfig`로 IPv4 주소 확인, 휴대폰과 같은 Wi-Fi, Windows 방화벽에서 8000 포트 허용)

## 3단계: 갤럭시 홈 미니 연결

[`bixby/README.md`](bixby/README.md) 참고. 요약:
1. 서버를 **HTTPS 공개 주소**로 노출 (Cloudflare Tunnel 등) + `.env`에 `BABYMIND_TOKEN` 설정
2. Bixby Developer Studio에서 캡슐을 만들어 `/log`를 호출
3. 같은 삼성 계정의 홈 미니에서 테스트

## API 요약

| Method | Path | 설명 |
|---|---|---|
| GET | `/health` | 상태 확인 |
| POST | `/log` | `{"text": "...", "source": "bixby"}` → 해석+저장, `speech`(읽어줄 문장) 반환 |
| GET | `/events?date=YYYY-MM-DD&days=7` | 기록 목록 |
| POST | `/events` | 구조화된 기록 직접 추가 |
| DELETE | `/events/{id}` | 삭제 |
| GET | `/summary` | 오늘 분유 합계/횟수, 수면, 기저귀 |
| POST | `/ask` | `{"question": "..."}` 기록 기반 답변 (키 없으면 오늘 요약) |

`BABYMIND_TOKEN`을 설정하면 `/health` 외 모든 요청에 헤더 `X-API-Key`(또는 `?key=`)가 필요합니다.
