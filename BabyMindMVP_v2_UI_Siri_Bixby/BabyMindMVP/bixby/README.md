# Bixby 연동

Samsung Bixby는 iOS의 App Intents와 같은 코드를 공유하지 않습니다. 현재 Samsung 공식 경로는 **Bixby Capsule / Samsung Automation Studio → HTTPS remote endpoint** 방식입니다.

이 프로젝트에는 서버의 `POST /voice/log` webhook을 추가했습니다.

## 테스트 구조
Bixby Voice → Capsule/Automation Studio → `https://YOUR_DOMAIN/voice/log` → BabyMind AI parser

요청 예시:
```json
{"text":"방금 분유 180 먹었어","timezone":"Asia/Seoul","source":"bixby"}
```

응답에는 `message`와 구조화된 `events`가 반환됩니다.

## 중요한 제한
현재 MVP의 iPhone 데이터는 SwiftData 로컬 저장이므로 Bixby가 만든 기록을 iPhone과 자동 공유하려면 **Cloud DB + 사용자 로그인**이 다음 단계로 필요합니다. `/voice/log`는 그 전 단계인 실제 Bixby 호출 가능한 서버 endpoint까지 구현한 것입니다.

Samsung Automation Studio에서 Capsule label / Bixby remote endpoint를 만들고 이 endpoint를 연결하세요. 공개 테스트에는 localhost가 아니라 HTTPS 공개 URL이 필요합니다.
