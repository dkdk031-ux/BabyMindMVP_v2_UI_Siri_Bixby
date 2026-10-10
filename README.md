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

## 빠른 시작 (거의 자동)

### 1. PC: 서버 켜기 — 더블클릭
| 파일 | 하는 일 |
|---|---|
| `start_server.bat` | 처음엔 자동 설치(가상환경·패키지·`.env`·인증 키 생성) 후 서버 실행. 꺼지면 자동 재시작 |
| `install_autostart.bat` | **PC 켤 때마다 서버 자동 실행** 등록 + 방화벽 8000 포트 허용(관리자 권한으로 실행) |
| `uninstall_autostart.bat` | 자동 실행 해제 |
| `start_server.sh` | Mac/Linux용 |

필요한 것: [Python](https://www.python.org/downloads/) 설치 (설치 화면에서 **Add python.exe to PATH** 체크).
서버 창과 `server/connection.txt`에 앱용 주소·인증 키가 표시됩니다.

### 2. 휴대폰: 앱 설치 — 빌드 자동
GitHub에 코드가 올라가면 **GitHub Actions가 APK를 자동으로 빌드**합니다.
휴대폰 브라우저로 저장소의 **Releases → `latest-apk` → BabyMind.apk** 를 눌러 설치하세요.
(처음 한 번 "출처를 알 수 없는 앱 설치 허용" 필요)

> 업데이트 APK를 기존 앱 위에 덮어 설치하려면 서명 키를 GitHub Secret으로 한 번 등록하세요 (아래 "선택 설정").
> 등록하지 않으면 업데이트할 때 기존 앱을 지우고 설치해야 합니다. 기록은 서버에 있어서 지워지지 않습니다.

### 3. 앱 실행 — 연결 자동
앱이 **같은 Wi-Fi에서 PC 서버를 자동으로 찾아** 주소와 인증 키를 설정합니다.
(PC IP가 바뀌어도 다시 자동으로 찾음. 못 찾으면 설정 화면에서 직접 입력)

### 4. Bixby용 공개 주소 — 자동
`server/.env`에서 `TUNNEL=1` 로 바꾸고 서버를 다시 켜면 cloudflared를 자동으로 내려받아
공개 HTTPS 주소를 만들고 화면에 표시합니다.

### 선택 설정
- `server/.env`의 `OPENAI_API_KEY`: 넣으면 복잡한 문장 해석과 AI 질문이 좋아짐 (없어도 기본 문장은 기록됨)
- 고정 서명 키 (APK 덮어 설치용), PC에서 한 번:
  ```bash
  keytool -genkeypair -keystore babymind.keystore -alias babymind -keyalg RSA -validity 36500 -storepass 원하는비번 -keypass 원하는비번 -dname "CN=BabyMind"
  # Windows PowerShell: [Convert]::ToBase64String([IO.File]::ReadAllBytes("babymind.keystore")) | Set-Clipboard
  # Mac/Linux:          base64 -i babymind.keystore | pbcopy
  ```
  GitHub 저장소 → Settings → Secrets and variables → Actions 에
  `ANDROID_KEYSTORE_BASE64`(복사한 값), `ANDROID_KEYSTORE_PASSWORD`(비번) 등록.
  keystore 파일은 저장소에 올리지 말고 따로 보관하세요.

### 직접 빌드/테스트 (개발용)
```bash
cd server && python -m pytest tests        # 서버 테스트
cd app && flutter run                      # 휴대폰 USB 연결 후 실행
```
API 문서: `http://PC주소:8000/docs`

규칙 파서가 이해하는 예:

| 말 | 저장 결과 |
|---|---|
| 우리애기 11시10분에 500ml 분유 먹었어 | 분유 500ml, 11:10 (오전/오후는 지금 기준 가장 최근 시각) |
| 방금 분유 180 먹었어 | 분유 180ml, 지금 |
| 20분 전에 응가했어 | 기저귀(대변), 20분 전 |
| 밤 11시부터 6시반까지 잤어 | 수면 7시간 30분 (자정 넘김 처리) |
| 체온 37.5도 | 체온 37.5℃ |

## 갤럭시 홈 미니 연결

[`bixby/README.md`](bixby/README.md) 참고. 요약:
1. `.env`에서 `TUNNEL=1` → 공개 HTTPS 주소 자동 생성 (인증 키는 이미 자동 생성됨)
2. Bixby Developer Studio에서 캡슐을 만들어 `/log`를 호출
3. 같은 삼성 계정의 홈 미니에서 테스트

## API 요약

| Method | Path | 설명 |
|---|---|---|
| GET | `/health` | 상태 확인 |
| GET | `/pair` | 같은 Wi-Fi의 앱에만 인증 키 전달 (앱 자동 연결용) |
| POST | `/log` | `{"text": "...", "source": "bixby"}` → 해석+저장, `speech`(읽어줄 문장) 반환 |
| GET | `/events?date=YYYY-MM-DD&days=7` | 기록 목록 |
| POST | `/events` | 구조화된 기록 직접 추가 |
| DELETE | `/events/{id}` | 삭제 |
| GET | `/summary` | 오늘 분유 합계/횟수, 수면, 기저귀 |
| POST | `/ask` | `{"question": "..."}` 기록 기반 답변 (키 없으면 오늘 요약) |

`BABYMIND_TOKEN`을 설정하면 `/health` 외 모든 요청에 헤더 `X-API-Key`(또는 `?key=`)가 필요합니다.
