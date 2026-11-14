"""Obsidian Inbox 제거 검증 테스트."""
import pytest
from fastapi.testclient import TestClient
from integrations.anki_connect import AnkiConnector


def test_dashboard_does_not_contain_obsidian_inbox(monkeypatch):
    """대시보드 응답 스키마에서 obsidian_inbox 필드가 완전히 제거되어야 한다."""
    monkeypatch.setattr(AnkiConnector, "invoke", staticmethod(lambda action, **p: 6 if action == "version" else []))
    import server

    client = TestClient(server.app)
    resp = client.get("/api/dashboard")
    assert resp.status_code == 200
    data = resp.json()
    assert "obsidian_inbox" not in data, "obsidian_inbox 필드가 여전히 존재합니다."


def test_workflow_extract_and_commit_routes_removed():
    """/api/workflow/extract 및 /commit 라우트가 제거되어 404(Not Found) 또는 405여야 한다."""
    import server

    client = TestClient(server.app)
    resp_extract = client.post("/api/workflow/extract")
    assert resp_extract.status_code == 404, f"extract 엔드포인트가 여전히 존재합니다 (code: {resp_extract.status_code})"

    resp_commit = client.post("/api/workflow/commit", json={"selected_sentences": [], "selected_vocab": []})
    assert resp_commit.status_code == 404, f"commit 엔드포인트가 여전히 존재합니다 (code: {resp_commit.status_code})"


def test_importer_service_module_removed():
    """importer_service 모듈이 제거되어 임포트되지 않아야 한다."""
    with pytest.raises(ImportError):
        import backend.services.importer_service  # noqa: F401
