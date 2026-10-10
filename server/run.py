"""BabyMind 서버 실행기 (개발: python run.py / 배포: BabyMind.exe).

BabyMind.exe 를 처음 실행하면:
- %LOCALAPPDATA%\\BabyMind 에 설치(자기 자신 복사) + PC 켤 때 자동 실행 등록
- .env 와 인증 키 자동 생성, 서버 실행(오류 시 자동 재시작)
- 브라우저로 앱 화면(http://localhost:8000) 열기
TUNNEL=1 이면 cloudflared를 자동 다운로드·실행해 Bixby용 공개 HTTPS 주소를 만든다.
"""
import os
import platform
import re
import secrets
import shutil
import socket
import subprocess
import sys
import threading
import time
import traceback
import urllib.request
import webbrowser

FROZEN = getattr(sys, "frozen", False)
CODE_DIR = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
if FROZEN:
    DATA_DIR = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "BabyMind")
else:
    DATA_DIR = os.path.dirname(os.path.abspath(__file__))
os.makedirs(DATA_DIR, exist_ok=True)

ENV = os.path.join(DATA_DIR, ".env")
TOOLS = os.path.join(DATA_DIR, "tools")
INFO_FILE = os.path.join(DATA_DIR, "connection.txt")
INSTALLED_EXE = os.path.join(DATA_DIR, "BabyMind.exe")
STARTUP_FILE = os.path.join(os.environ.get("APPDATA", ""), r"Microsoft\Windows\Start Menu\Programs\Startup\BabyMind.bat")

ENV_TEMPLATE = """# BabyMind 설정 (수정 후 BabyMind를 다시 실행하세요)
# 없으면 규칙 기반 파서로 동작 (기본 문장은 키 없이도 기록됨)
OPENAI_API_KEY=
OPENAI_MODEL=gpt-5.6-luna
PARSER=auto
BABYMIND_TOKEN={token}
TIMEZONE=Asia/Seoul
PORT=8000
# 1로 바꾸면 Bixby용 공개 HTTPS 주소(Cloudflare 임시 터널)를 자동으로 만듭니다
TUNNEL=0
CLOUDFLARE_TUNNEL_TOKEN=
PUBLIC_URL=
"""


def log(msg: str):
    print(f"[BabyMind] {msg}", flush=True)


def read_env() -> dict:
    values = {}
    if os.path.exists(ENV):
        for line in open(ENV, encoding="utf-8"):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                values[k.strip()] = v.strip()
    return values


def ensure_env() -> dict:
    if not os.path.exists(ENV):
        example = os.path.join(CODE_DIR, ".env.example")
        if not FROZEN and os.path.exists(example):
            shutil.copy(example, ENV)
        else:
            open(ENV, "w", encoding="utf-8").write(ENV_TEMPLATE.format(token=""))
        log(f"설정 파일을 만들었습니다: {ENV}")
    env = read_env()
    if not env.get("BABYMIND_TOKEN"):
        token = secrets.token_urlsafe(12)
        text = open(ENV, encoding="utf-8").read()
        if re.search(r"^BABYMIND_TOKEN=.*$", text, flags=re.M):
            text = re.sub(r"^BABYMIND_TOKEN=.*$", f"BABYMIND_TOKEN={token}", text, flags=re.M)
        else:
            text += f"\nBABYMIND_TOKEN={token}\n"
        open(ENV, "w", encoding="utf-8").write(text)
        log("인증 키를 자동 생성했습니다.")
        env = read_env()
    return env


def lan_ip() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"


def server_running(port: int) -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=2) as r:
            return b"babymind" in r.read()
    except Exception:
        return False


# ---------------- Windows 설치 / 자동 실행 ----------------
def install_windows() -> bool:
    """다운로드한 exe를 실행했으면 설치 위치로 복사하고 그쪽을 실행. 계속 진행해야 하면 True."""
    if not FROZEN or platform.system() != "Windows" or os.environ.get("BABYMIND_NO_INSTALL") == "1":
        return True
    me = os.path.abspath(sys.executable)
    if os.path.normcase(me) != os.path.normcase(INSTALLED_EXE):
        log("설치 중...")
        mypid = os.getpid()
        # 이전 버전이 실행 중이면 종료 (업데이트)
        subprocess.run(["taskkill", "/F", "/IM", "BabyMind.exe", "/FI", f"PID ne {mypid}"],
                       capture_output=True)
        for _ in range(10):
            try:
                shutil.copy2(me, INSTALLED_EXE)
                break
            except PermissionError:
                time.sleep(1)
        register_autostart()
        subprocess.Popen([INSTALLED_EXE, "--open"], creationflags=subprocess.CREATE_NEW_CONSOLE)
        log("설치 완료! 이 창은 곧 닫힙니다. 앞으로는 PC를 켜면 자동으로 실행됩니다.")
        time.sleep(3)
        return False
    register_autostart()
    return True


def register_autostart():
    try:
        os.makedirs(os.path.dirname(STARTUP_FILE), exist_ok=True)
        content = f'@start "BabyMind" /min "{INSTALLED_EXE}"\r\n'
        if not os.path.exists(STARTUP_FILE) or open(STARTUP_FILE, encoding="utf-8").read() != content:
            open(STARTUP_FILE, "w", encoding="utf-8").write(content)
            log("PC 시작 시 자동 실행을 등록했습니다.")
    except OSError as e:
        log(f"자동 실행 등록 실패: {e}")


# ---------------- Cloudflare 터널 (Bixby용) ----------------
def cloudflared_path() -> str | None:
    found = shutil.which("cloudflared")
    if found:
        return found
    system, machine = platform.system().lower(), platform.machine().lower()
    arch = "arm64" if machine in ("arm64", "aarch64") else "amd64"
    if system == "windows":
        name = f"cloudflared-windows-{arch}.exe"
    elif system == "linux":
        name = f"cloudflared-linux-{arch}"
    else:
        log("Mac은 'brew install cloudflared' 로 설치 후 다시 실행하세요.")
        return None
    local = os.path.join(TOOLS, "cloudflared.exe" if system == "windows" else "cloudflared")
    if not os.path.exists(local):
        os.makedirs(TOOLS, exist_ok=True)
        log("cloudflared 다운로드 중...")
        try:
            urllib.request.urlretrieve(f"https://github.com/cloudflare/cloudflared/releases/latest/download/{name}", local)
        except Exception as e:
            log(f"cloudflared 다운로드 실패: {e}")
            return None
        os.chmod(local, 0o755)
    return local


public_url = {"value": None}


def write_info(port: int, token: str):
    lines = [
        "==================== BabyMind 서버 ====================",
        f" PC에서 앱 화면      : http://localhost:{port}",
        f" 휴대폰 앱 서버 주소 : http://{lan_ip()}:{port}  (앱이 자동으로 찾음)",
        f" 인증 키             : {token}",
    ]
    if public_url["value"]:
        lines.append(f" 공개 주소(Bixby용)  : {public_url['value']}")
    lines += [f" 설정/데이터 폴더    : {DATA_DIR}", " 이 창을 닫으면 서버가 꺼집니다 (최소화해 두세요)",
              "======================================================="]
    text = "\n".join(lines)
    print("\n" + text + "\n", flush=True)
    open(INFO_FILE, "w", encoding="utf-8").write(text + "\n")


def run_tunnel(port: int, env: dict, token: str):
    exe = cloudflared_path()
    if not exe:
        return
    named = env.get("CLOUDFLARE_TUNNEL_TOKEN")
    if named:
        cmd = [exe, "tunnel", "--no-autoupdate", "run", "--token", named]
        public_url["value"] = env.get("PUBLIC_URL") or "(Cloudflare 대시보드에 설정한 주소)"
        write_info(port, token)
    else:
        cmd = [exe, "tunnel", "--no-autoupdate", "--url", f"http://localhost:{port}"]
    while True:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace")
        for line in proc.stdout:
            m = re.search(r"https://[a-z0-9-]+\.trycloudflare\.com", line)
            if m and m.group(0) != public_url["value"]:
                public_url["value"] = m.group(0)
                write_info(port, token)
                log("※ 임시 공개 주소는 재실행할 때마다 바뀝니다. Bixby 캡슐 config도 바꿔주세요.")
        proc.wait()
        log("터널이 끊겼습니다. 10초 후 다시 연결합니다.")
        time.sleep(10)


def main():
    if not install_windows():
        return
    env = ensure_env()
    for k, v in env.items():
        os.environ.setdefault(k, v)
    os.environ.setdefault("DB_PATH", os.path.join(DATA_DIR, "babymind.db"))
    port = int(env.get("PORT") or 8000)
    token = env.get("BABYMIND_TOKEN", "")

    if server_running(port):
        log("BabyMind 서버가 이미 실행 중입니다. 앱 화면을 엽니다.")
        webbrowser.open(f"http://localhost:{port}")
        time.sleep(2)
        return

    write_info(port, token)
    if env.get("TUNNEL", "0") == "1":
        threading.Thread(target=run_tunnel, args=(port, env, token), daemon=True).start()
    if "--open" in sys.argv:
        threading.Timer(2.5, lambda: webbrowser.open(f"http://localhost:{port}")).start()

    sys.path.insert(0, CODE_DIR)
    import uvicorn
    import main as app_module

    while True:
        try:
            uvicorn.run(app_module.app, host="0.0.0.0", port=port, log_level="warning")
            return  # Ctrl+C 등 정상 종료
        except KeyboardInterrupt:
            return
        except Exception:
            traceback.print_exc()
            log("서버 오류. 5초 후 자동 재시작합니다.")
            time.sleep(5)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        input("\n오류가 발생했습니다. 위 내용을 캡처해 알려주세요. (Enter로 종료)")
