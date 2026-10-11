"""대시보드 API는 화면이 쓰는 것만 계산한다. 링크 통계의 만성 오답은 노트(단어) 단위."""
import pytest
from fastapi.testclient import TestClient

from core import link_manager
from core.link_manager import LinkManager, init_db
from integrations.anki_connect import AnkiConnector


def test_dashboard_skips_unused_deck_stats(monkeypatch):
    calls = []

    def invoke(action, **p):
        calls.append(action)
        if action == "version":
            return 6
        return []

    monkeypatch.setattr(AnkiConnector, "invoke", staticmethod(invoke))
    from backend.routers import dashboard

    class NoInbox:
        def fetch_inbox_content(self):
            return None

    monkeypatch.setattr(dashboard, "ObsidianManager", NoInbox)
    import server
    r = TestClient(server.app).get("/api/dashboard")
    assert r.status_code == 200
    assert "findCards" not in calls and "cardsInfo" not in calls
    assert r.json()["connected"] is True


def test_link_stats_counts_leech_notes(monkeypatch, tmp_path):
    monkeypatch.setattr(link_manager, "DB_PATH", tmp_path / "links.db")
    init_db()
    seen = []

    def invoke(action, **p):
        seen.append(action)
        return [11, 12] if action == "findNotes" else [1, 2, 3, 4]

    monkeypatch.setattr(AnkiConnector, "invoke", staticmethod(invoke))
    assert LinkManager.get_stats()["leech_count"] == 2
    assert "findCards" not in seen


def test_corpus_audit_stats_reports_generated_at(monkeypatch, tmp_path):
    from backend.services import corpus_service
    f = tmp_path / "audit.json"
    f.write_text('{"total_notes": 3, "total_cards": 6, "tier_distribution": {}, "waste_leech_count": 0}', encoding="utf-8")
    monkeypatch.setattr(corpus_service, "AUDIT_JSON_PATH", f)
    res = corpus_service.CorpusService.get_audit_stats()
    assert res.total_notes == 3 and res.generated_at is not None


def test_inbox_unavailable_when_vault_folder_missing(monkeypatch, tmp_path):
    """서버처럼 Obsidian 볼트가 없으면 Inbox는 '사용 불가'이고, 파일을 만들려고 하지 않는다."""
    monkeypatch.setattr(AnkiConnector, "invoke", staticmethod(lambda action, **p: 6 if action == "version" else []))
    from backend.routers import dashboard

    touched = []

    class Spy:
        def fetch_inbox_content(self):
            touched.append(1)
            return {"vocab": [], "sentences": []}

    monkeypatch.setattr(dashboard, "ObsidianManager", Spy)
    monkeypatch.setattr(dashboard, "OBSIDIAN_VAULT_PATH", str(tmp_path / "no-vault"))
    import server
    inbox = TestClient(server.app).get("/api/dashboard").json()["obsidian_inbox"]
    assert inbox["available"] is False
    assert touched == []
