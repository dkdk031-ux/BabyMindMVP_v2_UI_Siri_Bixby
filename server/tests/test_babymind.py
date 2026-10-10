import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
TZ = ZoneInfo("Asia/Seoul")
NOW = datetime(2026, 10, 10, 11, 30, tzinfo=TZ)


def rules(text, now=NOW):
    from parser import parse_rules
    return parse_rules(text, now)


def test_speaker_sentence():
    [e] = rules("우리애기 11시10분에 500ml 분유 먹었어")
    assert e["type"] == "formula"
    assert e["started_at"] == "2026-10-10T11:10:00+09:00"
    assert (e["amount"], e["unit"]) == (500, "ml")


def test_wake_word_and_bare_amount():
    [e] = rules("하이빅스비 우리 애기 방금 분유 180 먹었어")
    assert (e["type"], e["amount"], e["unit"]) == ("formula", 180, "ml")
    assert e["started_at"] == "2026-10-10T11:30:00+09:00"


def test_ambiguous_hour_resolves_to_latest_past():
    evening = datetime(2026, 10, 10, 23, 40, tzinfo=TZ)
    [e] = rules("11시 10분에 분유 160 먹었어", evening)
    assert e["started_at"] == "2026-10-10T23:10:00+09:00"
    [e] = rules("7시에 분유 120", NOW)  # 오전 11:30 기준 7시 → 오전 7시
    assert e["started_at"] == "2026-10-10T07:00:00+09:00"


def test_sleep_range_over_midnight():
    morning = datetime(2026, 10, 10, 7, 0, tzinfo=TZ)
    [e] = rules("밤 11시부터 6시반까지 잤어", morning)
    assert e["type"] == "sleep"
    assert e["started_at"] == "2026-10-09T23:00:00+09:00"
    assert e["ended_at"] == "2026-10-10T06:30:00+09:00"


def test_relative_and_other_types():
    [e] = rules("20분 전에 응가했어")
    assert (e["type"], e["note"], e["started_at"]) == ("diaper", "대변", "2026-10-10T11:10:00+09:00")
    [e] = rules("체온 37.5도")
    assert (e["type"], e["amount"], e["unit"]) == ("temperature", 37.5, "℃")
    [e] = rules("1시간 전에 모유 15분 먹였어")
    assert (e["type"], e["amount"], e["started_at"]) == ("breastfeed", 15, "2026-10-10T10:30:00+09:00")


def test_describe():
    from parser import describe
    assert describe(rules("우리애기 11시10분에 500ml 분유 먹었어")[0]) == "오전 11시 10분 분유 500ml"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "t.db"))
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("BABYMIND_TOKEN", "secret")
    import importlib
    import main
    importlib.reload(main)
    from fastapi.testclient import TestClient
    return TestClient(main.app)


def test_api_flow(client):
    h = {"X-API-Key": "secret"}
    assert client.post("/log", json={"text": "분유 100"}).status_code == 401
    r = client.post("/log", json={"text": "우리애기 방금 분유 150ml 먹었어", "source": "bixby"}, headers=h).json()
    assert r["speech"].endswith("분유 150ml 기록했어요.")
    assert r["events"][0]["source"] == "bixby"
    client.post("/log?key=secret", json={"text": "방금 응가했어"})
    events = client.get("/events", headers=h).json()
    assert len(events) == 2
    s = client.get("/summary", headers=h).json()
    assert (s["formula_ml"], s["diaper_count"]) == (150, 1)
    assert "150ml" in client.post("/ask", json={"question": "오늘 얼마나 먹었어?"}, headers=h).json()["answer"]
    assert client.delete(f"/events/{events[0]['id']}", headers=h).json() == {"ok": True}
    assert len(client.get("/events", headers=h).json()) == 1


def test_pair_only_on_lan(client):
    from fastapi.testclient import TestClient
    import main
    assert client.get("/pair").status_code == 403
    lan = TestClient(main.app, client=("192.168.0.23", 50000))
    assert lan.get("/pair").json() == {"app": "babymind", "token": "secret"}
    assert lan.get("/pair", headers={"CF-Connecting-IP": "1.2.3.4"}).status_code == 403
    assert TestClient(main.app, client=("127.0.0.1", 50000)).get("/pair").status_code == 200
    assert TestClient(main.app, client=("8.8.8.8", 50000)).get("/pair").status_code == 403
