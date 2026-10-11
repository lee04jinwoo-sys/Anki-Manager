"""GET /api/stats/overview: Anki를 흉내낸 데이터로 응답 구조와 핵심 값을 확인한다."""
import datetime as dt
import time

import pytest
from fastapi.testclient import TestClient

from integrations.anki_connect import AnkiConnector

NOW = time.time()


def _ms(days_ago):
    # 지금 시각 기준 N일 전 1분 전: 실행 시각이 자정~새벽(하루 경계 전)이어도 같은 Anki 날짜에 들어간다
    return int((NOW - days_ago * 86400 - 60) * 1000)


@pytest.fixture
def client(monkeypatch):
    vocab = "1. Language::1.1. English::Vocabulary"
    rows = {
        vocab: [(_ms(0), 1, 0, 3, 30, 30, 2500, 60000, 1),   # 오늘 성숙 통과 1분
                (_ms(1), 1, 0, 1, 1, 25, 2500, 30000, 1),    # 어제 성숙 실패
                (_ms(1), 2, 0, 3, 5, 3, 2500, 30000, 1)],    # 어제 새싹 통과
        "1. Language::1.2. Japanese": [(_ms(2), 9, 0, 3, 5, 3, 2500, 60000, 1)],
    }

    def invoke(action, **p):
        if action == "deckNames":
            return list(rows) + ["1. Language::1.1. English::Sentence", "1. Language::1.1. English::Grammar"]
        if action == "cardReviews":
            return rows.get(p["deck"], [])
        if action == "getNumCardsReviewedByDay":
            return []
        if action == "multi":
            return [{"result": [1, 2] if "is:new" in a["params"]["query"] else [], "error": None} for a in p["actions"]]
        if action == "findCards":
            return []
        if action == "getDeckConfig":
            return {"desiredRetention": 0.9}
        raise AssertionError(action)

    monkeypatch.setattr(AnkiConnector, "invoke", staticmethod(invoke))
    import server
    return TestClient(server.app)


def test_overview_shape_and_values(client):
    r = client.get("/api/stats/overview")
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["today"]["reviews"] == 1 and d["today"]["minutes"] == 1.0
    assert d["habit"]["current"] == 3          # 오늘·어제·그제(일본어) 연속
    assert d["retention_30d"]["mature"] == {"reviews": 2, "passed": 1, "rate": 50.0}
    assert d["retention_30d"]["young"]["rate"] == 100.0
    assert len(d["heatmap"]) == 365 and len(d["forecast"]) == 14 and len(d["weekly_retention"]) == 12
    assert [x["label"] for x in d["decks"]] == ["Vocabulary", "Sentence", "Grammar"]
    assert d["decks"][0]["composition"]["new"] == 2 and d["decks"][0]["reviewed_today"] == 1
    assert d["desired_retention"] == 90.0


def test_overview_when_anki_offline(client, monkeypatch):
    def down(action, **p):
        raise Exception("AnkiConnect 에러: connection refused")
    monkeypatch.setattr(AnkiConnector, "invoke", staticmethod(down))
    r = client.get("/api/stats/overview")
    assert r.status_code == 503
