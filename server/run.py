"""BabyMind 서버 자동 실행기.

- .env가 없으면 만들고 인증 키(BABYMIND_TOKEN)를 자동 생성
- 서버(uvicorn) 실행, 비정상 종료 시 자동 재시작
- TUNNEL=1 이면 cloudflared를 자동 다운로드·실행해 Bixby용 공개 HTTPS 주소 생성
- 앱에 입력할 주소/키를 화면과 connection.txt에 표시
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
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ENV = os.path.join(HERE, ".env")
TOOLS = os.path.join(HERE, "tools")
INFO_FILE = os.path.join(HERE, "connection.txt")


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
        shutil.copy(os.path.join(HERE, ".env.example"), ENV)
        print("[BabyMind] .env 파일을 만들었습니다.")
    env = read_env()
    if not env.get("BABYMIND_TOKEN"):
        token = secrets.token_urlsafe(12)
        text = open(ENV, encoding="utf-8").read()
        if re.search(r"^BABYMIND_TOKEN=.*$", text, flags=re.M):
            text = re.sub(r"^BABYMIND_TOKEN=.*$", f"BABYMIND_TOKEN={token}", text, flags=re.M)
        else:
            text += f"\nBABYMIND_TOKEN={token}\n"
        open(ENV, "w", encoding="utf-8").write(text)
        print("[BabyMind] 인증 키를 자동 생성했습니다.")
        env = read_env()
    return env


def lan_ip() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"


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
        print("[BabyMind] Mac은 'brew install cloudflared' 로 설치 후 다시 실행하세요.")
        return None
    local = os.path.join(TOOLS, "cloudflared.exe" if system == "windows" else "cloudflared")
    if not os.path.exists(local):
        os.makedirs(TOOLS, exist_ok=True)
        url = f"https://github.com/cloudflare/cloudflared/releases/latest/download/{name}"
        print("[BabyMind] cloudflared 다운로드 중...")
        try:
            urllib.request.urlretrieve(url, local)
        except Exception as e:
            print(f"[BabyMind] cloudflared 다운로드 실패: {e}")
            return None
        os.chmod(local, 0o755)
    return local


public_url = {"value": None}


def write_info(port: int, token: str):
    lines = [
        "==================== BabyMind 서버 ====================",
        f" 앱 설정 > 서버 주소 : http://{lan_ip()}:{port}",
        f" 앱 설정 > 인증 키   : {token}",
    ]
    if public_url["value"]:
        lines.append(f" 공개 주소(Bixby용)  : {public_url['value']}")
    lines.append(" 종료: 이 창을 닫거나 Ctrl+C")
    lines.append("=======================================================")
    text = "\n".join(lines)
    print("\n" + text + "\n", flush=True)
    open(INFO_FILE, "w", encoding="utf-8").write(text + "\n")


def run_tunnel(port: int, env: dict, token: str):
    exe = cloudflared_path()
    if not exe:
        return
    named = env.get("CLOUDFLARE_TUNNEL_TOKEN")
    if named:
        # Cloudflare 계정의 고정 터널: 주소가 바뀌지 않는다 (PUBLIC_URL에 그 주소를 적어둔다)
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
                print("[BabyMind] ※ 임시 공개 주소는 재실행할 때마다 바뀝니다. Bixby 캡슐 config도 바꿔주세요.")
        proc.wait()
        print("[BabyMind] 터널이 끊겼습니다. 10초 후 다시 연결합니다.")
        time.sleep(10)


def main():
    env = ensure_env()
    port = int(env.get("PORT") or 8000)
    token = env.get("BABYMIND_TOKEN", "")
    write_info(port, token)

    if env.get("TUNNEL", "0") == "1":
        threading.Thread(target=run_tunnel, args=(port, env, token), daemon=True).start()

    cmd = [sys.executable, "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", str(port)]
    while True:
        proc = subprocess.Popen(cmd, cwd=HERE)
        try:
            code = proc.wait()
        except KeyboardInterrupt:
            proc.terminate()
            print("\n[BabyMind] 서버를 종료합니다.")
            return
        print(f"[BabyMind] 서버가 종료되었습니다(코드 {code}). 5초 후 자동 재시작합니다. 끄려면 창을 닫으세요.")
        try:
            time.sleep(5)
        except KeyboardInterrupt:
            return


if __name__ == "__main__":
    main()
