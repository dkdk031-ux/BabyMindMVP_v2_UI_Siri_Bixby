import ipaddress
import json
import os
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from pydantic import BaseModel

load_dotenv()

import db  # noqa: E402  (.env를 먼저 읽어야 DB_PATH가 반영됨)
from parser import EVENT_TYPES, TYPE_NAMES, describe, parse_text  # noqa: E402

TZ = ZoneInfo(os.getenv("TIMEZONE", "Asia/Seoul"))
app = FastAPI(title="BabyMind API")
db.init_db()


def check_key(x_api_key: str | None = Header(None), key: str | None = Query(None)):
    """BABYMIND_TOKEN을 설정하면 헤더 X-API-Key(또는 ?key=)가 일치해야 한다."""
    token = os.getenv("BABYMIND_TOKEN")
    if token and token not in (x_api_key, key):
        raise HTTPException(401, "인증 키가 올바르지 않습니다.")


auth = [Depends(check_key)]


class LogIn(BaseModel):
    text: str
    source: str = "app"


class EventIn(BaseModel):
    type: str
    started_at: str
    ended_at: str | None = None
    amount: float | None = None
    unit: str | None = None
    note: str | None = None


class AskIn(BaseModel):
    question: str


def day_range(d: date) -> tuple[str, str]:
    start = datetime(d.year, d.month, d.day, tzinfo=TZ)
    return start.isoformat(timespec="seconds"), (start + timedelta(days=1)).isoformat(timespec="seconds")


def summarize(events: list[dict]) -> dict:
    formula = [e for e in events if e["type"] == "formula"]
    sleep_min = sum(
        (datetime.fromisoformat(e["ended_at"]) - datetime.fromisoformat(e["started_at"])).total_seconds() // 60
        for e in events if e["type"] == "sleep" and e["ended_at"])
    return {
        "formula_ml": sum(e["amount"] or 0 for e in formula),
        "formula_count": len(formula),
        "sleep_min": int(sleep_min),
        "diaper_count": sum(1 for e in events if e["type"] == "diaper"),
        "last_formula_at": max((e["started_at"] for e in formula), default=None),
    }


@app.get("/health")
def health():
    return {"ok": True, "app": "babymind", "openai": bool(os.getenv("OPENAI_API_KEY")),
            "auth": bool(os.getenv("BABYMIND_TOKEN"))}


@app.get("/pair")
def pair(request: Request):
    """같은 Wi-Fi의 앱이 서버를 자동으로 찾아 인증 키를 받아가는 용도.
    인터넷(Cloudflare 터널)을 거친 요청에는 알려주지 않는다."""
    try:
        ip = ipaddress.ip_address(request.client.host if request.client else "")
    except ValueError:
        ip = None
    via_tunnel = any(h.lower().startswith("cf-") for h in request.headers)
    # PC 자신(브라우저 앱)은 허용. 터널 요청은 cf- 헤더가 붙고, uvicorn이 실제 접속 IP로 바꿔주므로 걸러진다.
    if ip is None or not (ip.is_private or ip.is_loopback) or via_tunnel:
        raise HTTPException(403, "같은 Wi-Fi에서만 연결할 수 있습니다.")
    return {"app": "babymind", "token": os.getenv("BABYMIND_TOKEN", "")}


@app.post("/log", dependencies=auth)
def log(req: LogIn):
    """음성/텍스트 한 문장을 해석해 저장. 앱, Bixby, 스피커 모두 이 endpoint를 사용한다."""
    text = req.text.strip()
    if not text:
        raise HTTPException(400, "기록할 내용이 없습니다.")
    now = datetime.now(TZ)
    try:
        parsed, used = parse_text(text, now)
    except Exception as e:
        raise HTTPException(502, f"해석 실패: {e}")
    saved = [db.insert_event(e, req.source, text, TZ) for e in parsed if e.get("type") in EVENT_TYPES]
    if not saved:
        return {"speech": "무엇을 기록할지 이해하지 못했어요. 다시 말해 주세요.", "events": [], "parser": used}
    speech = ", ".join(describe(e) for e in saved) + " 기록했어요."
    return {"speech": speech, "events": saved, "parser": used}


@app.post("/events", dependencies=auth)
def add_event(e: EventIn):
    if e.type not in EVENT_TYPES:
        raise HTTPException(400, f"type은 {EVENT_TYPES} 중 하나여야 합니다.")
    try:
        return db.insert_event(e.model_dump(), "app", None, TZ)
    except ValueError as err:
        raise HTTPException(400, f"시간 형식 오류: {err}")


@app.get("/events", dependencies=auth)
def get_events(day: date | None = Query(None, alias="date"), days: int = Query(1, ge=1, le=60)):
    """date(기본 오늘)부터 거꾸로 days일 동안의 기록."""
    end_day = day or datetime.now(TZ).date()
    start, _ = day_range(end_day - timedelta(days=days - 1))
    _, end = day_range(end_day)
    return db.list_events(start, end)


@app.delete("/events/{event_id}", dependencies=auth)
def remove_event(event_id: int):
    if not db.delete_event(event_id):
        raise HTTPException(404, "기록을 찾을 수 없습니다.")
    return {"ok": True}


@app.get("/summary", dependencies=auth)
def summary(day: date | None = Query(None, alias="date")):
    d = day or datetime.now(TZ).date()
    return {"date": d.isoformat(), **summarize(db.list_events(*day_range(d)))}


def summary_speech(s: dict) -> str:
    text = f"오늘 분유 {s['formula_count']}번, 총 {int(s['formula_ml'])}ml 먹었고, 기저귀는 {s['diaper_count']}번 갈았어요."
    if s["sleep_min"]:
        text += f" 잠은 {s['sleep_min'] // 60}시간 {s['sleep_min'] % 60}분 잤어요."
    return text


@app.post("/ask", dependencies=auth)
def ask(req: AskIn):
    now = datetime.now(TZ)
    today = summarize(db.list_events(*day_range(now.date())))
    if not os.getenv("OPENAI_API_KEY"):
        return {"answer": summary_speech(today)}
    start, _ = day_range(now.date() - timedelta(days=2))
    events = db.list_events(start, day_range(now.date())[1])
    data = json.dumps([{k: e[k] for k in ("type", "started_at", "ended_at", "amount", "unit", "note")}
                       for e in events], ensure_ascii=False)
    try:
        from openai import OpenAI
        r = OpenAI().responses.create(model=os.getenv("OPENAI_MODEL", "gpt-5.6-luna"), input=[
            {"role": "system", "content": "너는 육아 기록 도우미다. 제공된 실제 기록만 근거로 정확하고 짧게 한국어로 답한다. "
                                          "스피커가 읽어줄 수 있게 1~2문장으로 답한다. 없는 사실은 추측하지 않고 의료 진단은 하지 않는다. "
                                          f"현재 시각: {now.isoformat()}. 타입 이름: {json.dumps(TYPE_NAMES, ensure_ascii=False)}"},
            {"role": "user", "content": f"질문: {req.question}\n최근 3일 기록(JSON): {data}"}])
        return {"answer": r.output_text}
    except Exception:
        return {"answer": summary_speech(today)}


def _web_dir() -> str | None:
    """Flutter 웹 빌드(앱 화면)를 찾아 http://localhost:8000 에서 보여준다."""
    import sys
    here = os.path.dirname(os.path.abspath(__file__))
    for d in (os.getenv("WEB_DIR"), os.path.join(getattr(sys, "_MEIPASS", here), "web"),
              os.path.join(here, "..", "app", "build", "web")):
        if d and os.path.exists(os.path.join(d, "index.html")):
            return d
    return None


if _web_dir():
    from fastapi.staticfiles import StaticFiles
    app.mount("/", StaticFiles(directory=_web_dir(), html=True), name="web")
