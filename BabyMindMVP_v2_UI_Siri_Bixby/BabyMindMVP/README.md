# BabyMind MVP

실제로 동작하는 iPhone SwiftUI + FastAPI + OpenAI API 최소제품입니다.

## 1. 서버 실행 (Mac)
```bash
cd server
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# .env에 OPENAI_API_KEY 입력
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```
브라우저에서 `http://127.0.0.1:8000/health` 확인.

## 2. Xcode 프로젝트 만들기
Xcode > New Project > iOS App
- Product Name: BabyMind
- Interface: SwiftUI
- Language: Swift
- Storage: SwiftData
- Deployment target: iOS 17+

자동 생성된 Swift 파일 대신 `BabyMindApp/` 폴더의 5개 Swift 파일을 프로젝트에 추가합니다.

## 3. 권한 추가
Target > Info에 아래 Privacy 항목 추가:
- Privacy - Microphone Usage Description: `육아 기록을 음성으로 입력하기 위해 마이크를 사용합니다.`
- Privacy - Speech Recognition Usage Description: `음성을 육아 기록으로 변환하기 위해 음성 인식을 사용합니다.`

로컬 HTTP 개발 서버를 쓰려면 Info.plist에 개발 중에만 ATS 예외를 추가하거나, HTTPS 터널/서버를 사용하세요. App Store 배포판에서는 HTTPS를 사용하세요.

## 4. 실제 iPhone에서 서버 연결
Mac과 iPhone을 같은 Wi-Fi에 연결하고 Mac의 IP를 확인합니다.
예: `192.168.0.10`

`APIClient.swift`:
```swift
var baseURL = URL(string: "http://192.168.0.10:8000")!
```
Mac 방화벽에서 Python/8000 포트 연결을 허용합니다.

## 5. 테스트
앱에서 다음을 입력하거나 말합니다.
- `7시 20분에 분유 180 먹었어`
- `8시부터 9시 반까지 잤어`
- `방금 응가했어`
- `오늘 총 몇 ml 먹었어?` → AI에게 질문

## 현재 MVP 범위
- 한국어 음성인식
- GPT Structured Output 기반 자연어 → 육아 Event 변환
- 복수 Event 추출
- SwiftData 로컬 저장
- 오늘 타임라인
- 삭제
- 저장된 기록 기반 AI 질문

## 다음 상용화 작업
로그인/가족공유, Cloud DB, 인증, HTTPS, 서버 집계 Function Calling, Siri/App Intents, Widget/Watch, 결제, 개인정보 동의/삭제/Export, rate limit, monitoring, AI eval을 추가해야 합니다.

## 보안
API Key를 Swift 코드에 넣지 마세요. `.env`는 Git에 커밋하지 마세요.

## v2 추가: UI + Siri + Bixby bridge

- 홈 대시보드/오늘 요약/최근 기록/대형 음성 버튼/AI 탭으로 UI 개편
- `AppIntents.swift` 추가: Siri/Shortcuts에서 **베이비 기록**, **AI 질문** 노출
- Xcode에서 App Intents가 포함되도록 파일을 Target Membership에 추가하세요.
- 권장 Siri 문구: “Siri야, BabyMind에 기록해” → Siri가 기록 내용을 질문 → “분유 180 먹었어”
- Bixby용 서버 webhook: `POST /voice/log`
- `bixby/README.md`에 Samsung Automation Studio/Capsule 연결 방법 수록

> Siri는 iPhone 앱의 로컬 기록으로 이어지지만, Bixby는 Samsung 기기에서 호출되므로 iPhone과 완전 동기화하려면 다음 버전에서 로그인 + Cloud DB가 필요합니다.
