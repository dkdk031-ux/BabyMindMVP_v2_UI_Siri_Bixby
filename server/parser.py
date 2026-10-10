"""한국어 육아 문장 → 기록(Event) 변환.

- OPENAI_API_KEY가 있으면 OpenAI로 파싱(여러 기록 동시 추출 가능)
- 없거나 실패하면 규칙 기반 파서로 처리 (예: "11시10분에 500ml 분유 먹었어")
"""
import json
import os
import re
from datetime import datetime, timedelta

EVENT_TYPES = ["formula", "breastfeed", "sleep", "diaper", "meal", "medicine", "temperature", "memo"]
TYPE_NAMES = {"formula": "분유", "breastfeed": "모유", "sleep": "수면", "diaper": "기저귀",
              "meal": "식사", "medicine": "약", "temperature": "체온", "memo": "메모"}

# 호출어/애칭은 기록 내용이 아니므로 제거
WAKE_WORDS = re.compile(r"^\s*(하이\s*)?빅스비[\s,]*|우리\s*(애기|아기|아가)(한테|에게|가|는|에)?\s*")

# (키워드, 타입, 메모) — 앞에 있는 것이 우선
KEYWORDS = [
    (r"분유", "formula", None),
    (r"모유|수유|젖", "breastfeed", None),
    (r"이유식|밥|간식|우유", "meal", None),
    (r"체온|열이|열 ", "temperature", None),
    (r"해열제|약", "medicine", None),
    (r"응가|똥|대변", "diaper", "대변"),
    (r"쉬했|쉬 했|소변", "diaper", "소변"),
    (r"기저귀", "diaper", None),
    (r"낮잠|잠들|잤|재웠|자기 시작|잠", "sleep", None),
]

UNIT_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(ml|mL|ML|밀리리터|밀리|미리|cc|씨씨|g|그램|도|℃)")
UNIT_MAP = {"ml": "ml", "mL": "ml", "ML": "ml", "밀리리터": "ml", "밀리": "ml", "미리": "ml",
            "cc": "ml", "씨씨": "ml", "g": "g", "그램": "g", "도": "℃", "℃": "℃"}

TIME_RE = re.compile(
    r"(?:(오전|오후|아침|낮|저녁|밤|새벽)\s*)?(\d{1,2})\s*(?:시(?!간)\s*(?:(\d{1,2})\s*분|(반))?|:(\d{2}))"
)


def _resolve_hour(period: str | None, hour: int, minute: int, now: datetime) -> datetime:
    """'11시10분'처럼 오전/오후가 없으면 지금 기준 가장 최근의 과거 시각으로 해석."""
    base = now.replace(second=0, microsecond=0)
    if period in ("오후", "저녁", "밤") and hour < 12:
        hour += 12
    if period == "낮" and hour < 7:
        hour += 12
    if period in ("오전", "새벽", "아침") and hour == 12:
        hour = 0
    if period or hour >= 12:
        candidates = [hour % 24]
    else:
        candidates = [hour, hour + 12]
    tolerance = timedelta(minutes=10)  # 살짝 미래 시각도 오늘로 인정
    best = None
    for day_offset in (0, -1):
        for h in candidates:
            t = base.replace(hour=h % 24, minute=minute) + timedelta(days=day_offset)
            if t <= now + tolerance and (best is None or t > best):
                best = t
        if best:
            break
    return best


def _parse_times(text: str, now: datetime) -> tuple[datetime, datetime | None]:
    m = re.search(r"(\d+)\s*분\s*전", text)
    if m:
        return now - timedelta(minutes=int(m.group(1))), None
    m = re.search(r"(\d+)\s*시간\s*(반\s*)?전", text)
    if m:
        return now - timedelta(hours=int(m.group(1)), minutes=30 if m.group(2) else 0), None

    times = []
    for tm in TIME_RE.finditer(text):
        hour = int(tm.group(2))
        if hour > 24:
            continue
        minute = 30 if tm.group(4) else int(tm.group(3) or tm.group(5) or 0)
        if minute > 59:
            continue
        times.append((tm, _resolve_hour(tm.group(1), hour % 24, minute, now)))

    if not times:
        return now.replace(second=0, microsecond=0), None
    start = times[0][1]
    end = None
    if len(times) >= 2 and re.search(r"부터|에서|~|-", text):
        end = times[1][1]
        if end < start:
            # "밤 11시부터 2시까지"처럼 자정을 넘긴 경우
            if end + timedelta(days=1) <= now + timedelta(minutes=10):
                end += timedelta(days=1)
            else:
                start -= timedelta(days=1)
    return start, end


def _detect_type(text: str) -> tuple[str, str | None]:
    for pattern, etype, note in KEYWORDS:
        if re.search(pattern, text):
            return etype, note
    return "memo", None


def parse_rules(text: str, now: datetime) -> list[dict]:
    cleaned = WAKE_WORDS.sub("", text).strip()
    if not cleaned:
        return []
    etype, note = _detect_type(cleaned)
    start, end = _parse_times(cleaned, now)

    amount, unit = None, None
    m = UNIT_RE.search(cleaned)
    if m:
        amount, unit = float(m.group(1)), UNIT_MAP[m.group(2)]
    elif etype in ("formula", "breastfeed", "meal"):
        # "분유 180" 처럼 단위 없이 말한 숫자 (시각 숫자는 제외)
        no_time = TIME_RE.sub(" ", cleaned)
        no_time = re.sub(r"\d+\s*(분|시간)\s*전", " ", no_time)
        m = re.search(r"(\d+(?:\.\d+)?)", no_time)
        if m:
            amount, unit = float(m.group(1)), ("ml" if etype == "formula" else None)
    if etype == "breastfeed" and unit is None and amount is not None:
        unit = "분"
    if etype == "temperature" and amount is not None and unit is None:
        unit = "℃"

    if etype == "memo":
        note = cleaned
    return [{
        "type": etype,
        "started_at": start.isoformat(timespec="seconds"),
        "ended_at": end.isoformat(timespec="seconds") if end else None,
        "amount": amount,
        "unit": unit,
        "note": note,
    }]


SCHEMA = {"type": "object", "properties": {"events": {"type": "array", "items": {"type": "object", "properties": {
    "type": {"type": "string", "enum": EVENT_TYPES},
    "started_at": {"type": "string"}, "ended_at": {"type": ["string", "null"]},
    "amount": {"type": ["number", "null"]}, "unit": {"type": ["string", "null"]},
    "note": {"type": ["string", "null"]}},
    "required": ["type", "started_at", "ended_at", "amount", "unit", "note"], "additionalProperties": False}}},
    "required": ["events"], "additionalProperties": False}


def parse_openai(text: str, now: datetime) -> list[dict]:
    from openai import OpenAI

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    r = client.responses.create(
        model=os.getenv("OPENAI_MODEL", "gpt-5.6-luna"),
        input=[{"role": "system", "content": f"""너는 한국어 육아기록 파서다. 현재 시각은 {now.isoformat()}.
'우리애기', '하이빅스비' 같은 호출어는 무시한다. 상대시간(방금, 아까, 11시10분)은 현재 시각 기준 가장 최근의 과거 시각으로 해석해 ISO8601(+09:00)로 변환한다.
분유=formula, 모유=breastfeed, 잠/낮잠=sleep, 응가/쉬/기저귀=diaper, 이유식/밥=meal, 약=medicine, 체온=temperature, 그 외=memo.
분유 양 단위는 ml. 한 문장에 여러 기록이 있으면 모두 분리한다. 확실하지 않은 값은 null. 의료적 판단은 하지 않는다."""},
               {"role": "user", "content": text}],
        text={"format": {"type": "json_schema", "name": "baby_events", "strict": True, "schema": SCHEMA}},
    )
    return json.loads(r.output_text)["events"]


def parse_text(text: str, now: datetime) -> tuple[list[dict], str]:
    """기록 목록과 사용한 파서 이름을 반환."""
    mode = os.getenv("PARSER", "auto")
    if mode != "rules" and os.getenv("OPENAI_API_KEY"):
        try:
            return parse_openai(text, now), "openai"
        except Exception:
            if mode == "openai":
                raise
    return parse_rules(text, now), "rules"


def describe(event: dict) -> str:
    """스피커가 읽어줄 짧은 문장. 예: '11시 10분 분유 500ml'"""
    start = datetime.fromisoformat(event["started_at"])
    hour12 = start.hour % 12 or 12
    when = f"{'오전' if start.hour < 12 else '오후'} {hour12}시" + (f" {start.minute}분" if start.minute else "")
    s = f"{when} {TYPE_NAMES.get(event['type'], event['type'])}"
    if event.get("amount") is not None:
        a = event["amount"]
        s += f" {int(a) if float(a).is_integer() else a}{event.get('unit') or ''}"
    if event.get("ended_at"):
        mins = int((datetime.fromisoformat(event["ended_at"]) - start).total_seconds() // 60)
        s += f" {mins // 60}시간 {mins % 60}분" if mins >= 60 else f" {mins}분"
    if event["type"] == "diaper" and event.get("note"):
        s += f"({event['note']})"
    return s
