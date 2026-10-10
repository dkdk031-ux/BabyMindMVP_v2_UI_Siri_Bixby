# 갤럭시 홈 미니(Bixby) 연결

## 원리

```
"하이빅스비, 우리애기 11시10분에 500ml 분유 먹었어"
   └▶ Bixby가 음성을 텍스트로 변환
       └▶ BabyMind 캡슐(LogBaby.js)이 서버 POST /log 호출  (헤더 X-API-Key)
           └▶ 서버가 해석·저장 → {"speech": "오전 11시 10분 분유 500ml 기록했어요."}
               └▶ 스피커가 speech를 읽어줌 / 휴대폰 앱에는 15초 안에 표시
```

서버는 이미 이 흐름을 지원합니다. 남은 것은 **① 서버를 인터넷에 공개**와 **② Bixby 캡슐 등록**입니다.

## ① 서버를 HTTPS로 공개

Bixby는 삼성 클라우드에서 서버를 호출하므로 `192.168.x.x` 같은 집 내부 주소로는 닿지 않습니다.

1. `server/.env`에서 `TUNNEL=1` 로 바꾸고 `start_server.bat` 재실행
   → cloudflared가 자동 설치되고 서버 창에 `공개 주소(Bixby용) : https://xxxx.trycloudflare.com` 이 표시됩니다.
   인증 키(`BABYMIND_TOKEN`)는 첫 실행 때 이미 자동 생성되어 있습니다.
2. 임시 주소는 재실행할 때마다 바뀝니다. 고정하려면 Cloudflare 계정에서 터널을 만들고
   `.env`에 `CLOUDFLARE_TUNNEL_TOKEN`, `PUBLIC_URL`을 넣으면 같은 주소로 자동 연결됩니다.
3. 확인:
   ```bash
   curl -X POST https://xxxx.trycloudflare.com/log \
     -H "Content-Type: application/json" -H "X-API-Key: 내토큰" \
     -d '{"text":"우리애기 11시10분에 500ml 분유 먹었어","source":"bixby"}'
   ```

## ② Bixby 캡슐 (`bixby/capsule/` 초안)

> ⚠️ 이 캡슐 파일은 **초안이며 아직 Bixby Developer Studio에서 빌드·테스트하지 않았습니다.**
> 삼성의 캡슐 개발 정책(Developer Studio 제공 여부, 스피커 target 지원, 비공개 테스트 방법)이 바뀌었을 수 있으니 먼저 확인하세요.

1. [Bixby Developer Center](https://bixbydevelopers.com)에서 Bixby Developer Studio 설치, 삼성 계정 로그인
2. 새 캡슐 생성 후 `bixby/capsule/`의 파일을 같은 위치에 복사
   - `capsule.bxb`의 `targets`는 Studio가 제안하는 값으로 (가능하면 스피커 target 추가)
3. Studio > Configuration & Secrets 에서
   - config `server.url` = ①의 HTTPS 주소
   - secret `babymind.token` = `BABYMIND_TOKEN` 값
4. Training 탭에서 `resources/ko-KR/training-examples.txt`의 문장들을 Goal `LogBaby`로 학습시키고,
   "우리애기" 뒤의 기록 문장 전체를 `LogText` 값으로 지정
5. Simulator에서 테스트 → 내 계정 기기(홈 미니)로 개인 테스트 배포

### 호출 문구에 대해
Bixby는 보통 **캡슐 이름을 함께 말해야** 캡슐이 실행됩니다. 캡슐 이름을 "우리애기"로 정하면
"하이빅스비, 우리애기 11시10분에 분유 500 먹었어"에 가깝게 쓸 수 있습니다.
실제로 인식되는 문장 형태는 Studio 시뮬레이터에서 확인해야 합니다.

## 캡슐이 어려울 때의 대안

| 방법 | 장점 | 한계 |
|---|---|---|
| **휴대폰 앱 마이크** (지금 바로 가능) | 설정 없음 | 휴대폰을 들어야 함 |
| Bixby **빠른 명령어** + SmartThings 루틴 | 코딩 없음 | 자유 문장(시간·양) 전달이 안 됨 → "분유 기록" 같은 고정 버튼만 가능 |
| 구글 어시스턴트/다른 스피커 | 웹훅 연동 도구가 많음 | 갤럭시 홈 미니가 아님 |
