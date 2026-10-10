import os, json
from datetime import datetime
from zoneinfo import ZoneInfo
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv(); app = FastAPI(title="BabyMind API")
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
MODEL = os.getenv("OPENAI_MODEL", "gpt-5.6-luna")

class ParseIn(BaseModel): text: str; timezone: str = "Asia/Seoul"
class AskIn(BaseModel): question: str; events: list[dict]

SCHEMA = {"type":"object","properties":{"events":{"type":"array","items":{"type":"object","properties":{
 "type":{"type":"string","enum":["formula","breastfeed","sleep","diaper","meal","medicine","temperature","memo"]},
 "started_at":{"type":"string"},"ended_at":{"type":["string","null"]},"amount":{"type":["number","null"]},
 "unit":{"type":["string","null"]},"note":{"type":["string","null"]}},
 "required":["type","started_at","ended_at","amount","unit","note"],"additionalProperties":False}}},"required":["events"],"additionalProperties":False}

@app.get("/health")
def health(): return {"ok": True, "model": MODEL}

@app.post("/parse")
def parse(req: ParseIn):
    now = datetime.now(ZoneInfo(req.timezone)).isoformat()
    try:
        r = client.responses.create(model=MODEL,
          input=[{"role":"system","content":f"""너는 한국어 육아기록 파서다. 현재 시각은 {now}. 사용자의 상대시간(방금, 아까, 오늘 7시)을 합리적으로 ISO8601(+09:00)로 변환한다. 분유= formula, 모유=breastfeed, 잠/낮잠= sleep, 응가/쉬/기저귀=diaper, 이유식/밥=meal, 약=medicine, 체온=temperature. 한 문장에 여러 기록이 있으면 모두 분리한다. 확실하지 않은 값은 null로 둔다. 의료적 판단은 하지 않는다."""}, {"role":"user","content":req.text}],
          text={"format":{"type":"json_schema","name":"baby_events","strict":True,"schema":SCHEMA}})
        return json.loads(r.output_text)
    except Exception as e: raise HTTPException(500, str(e))

@app.post("/ask")
def ask(req: AskIn):
    try:
        # MVP: 최근 이벤트만 전달. 상용 버전은 서버 집계/Function Calling으로 교체.
        data = json.dumps(req.events[-200:], ensure_ascii=False)
        r = client.responses.create(model=MODEL, input=[
          {"role":"system","content":"너는 육아 기록 도우미다. 제공된 실제 기록만 근거로 정확하고 짧게 한국어로 답한다. 없는 사실은 추측하지 않는다. 의료 진단은 하지 않는다."},
          {"role":"user","content":f"질문: {req.question}\n기록(JSON): {data}"}])
        return {"answer": r.output_text}
    except Exception as e: raise HTTPException(500, str(e))

class VoiceWebhookIn(BaseModel):
    text: str
    timezone: str = "Asia/Seoul"
    source: str = "bixby"

@app.post("/voice/log")
def voice_log(req: VoiceWebhookIn):
    """Bixby/외부 음성 플랫폼용 공용 webhook. 상용화 시 사용자 인증 + cloud DB 저장을 연결한다."""
    parsed = parse(ParseIn(text=req.text, timezone=req.timezone))
    return {"message": f"{len(parsed.get('events', []))}개 육아 기록을 이해했어요.", "events": parsed.get("events", [])}
