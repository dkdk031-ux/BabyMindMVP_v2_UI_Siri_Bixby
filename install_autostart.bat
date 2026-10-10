@echo off
chcp 65001 >nul
rem PC를 켜고 로그인하면 BabyMind 서버가 자동으로 (최소화 상태로) 실행되도록 등록합니다.
set "STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
> "%STARTUP%\BabyMind.bat" echo @start "BabyMind" /min cmd /c ""%~dp0start_server.bat""
echo [BabyMind] 자동 실행 등록 완료: %STARTUP%\BabyMind.bat

rem 휴대폰에서 접속할 수 있게 방화벽 8000 포트 허용 (관리자 권한 필요)
netsh advfirewall firewall show rule name="BabyMind 8000" >nul 2>nul || (
  netsh advfirewall firewall add rule name="BabyMind 8000" dir=in action=allow protocol=TCP localport=8000 profile=private >nul 2>nul ^
    && echo [BabyMind] 방화벽 8000 포트 허용 완료 ^
    || echo [BabyMind] 방화벽 등록은 관리자 권한이 필요합니다. 이 파일을 우클릭 ^> "관리자 권한으로 실행" 하세요.
)

echo.
echo 지금 바로 서버를 시작합니다...
start "BabyMind" /min cmd /c ""%~dp0start_server.bat""
pause
