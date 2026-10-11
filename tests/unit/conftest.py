import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


@pytest.fixture(autouse=True)
def _block_real_anki(monkeypatch):
    """모킹하지 않은 AnkiConnect 호출이 실제 Anki로 나가지 않게 막는다."""
    from integrations import anki_connect

    def _refuse(*args, **kwargs):
        raise AssertionError("unit test attempted a real AnkiConnect HTTP call")

    monkeypatch.setattr(anki_connect._SESSION, "post", _refuse)


@pytest.fixture(autouse=True)
def _isolate_local_dbs(monkeypatch, tmp_path):
    """테스트가 실제 data/ 의 로컬 DB(처리 기록·LLM 캐시)에 쓰지 않게 한다."""
    from backend.services import corpus_service, leech_history

    monkeypatch.setattr(leech_history, "DB_PATH", tmp_path / "leech_treatments.db")
    monkeypatch.setattr(corpus_service, "LLM_CACHE_PATH", tmp_path / "llm_cache.db")
