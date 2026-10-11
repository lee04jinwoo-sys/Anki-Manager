"""토큰·속도 개선: 청크 후보 모델/캐시, Leech 목록 캐시, 정규식 캐시."""
import json

import pytest

from backend.services import corpus_service as cs
from core import link_manager
from core.link_manager import LinkManager, PatternMatcher, init_db
from integrations.anki_connect import AnkiConnector

CANDS = {"candidates": [{"chunk": "lurk in the shadows", "meaning": "그림자 속에 숨어 있다", "pos": "v",
                         "example_1": "a", "trans_1": "b", "example_2": "c", "trans_2": "d", "explanation": "e"}]}


@pytest.fixture
def gemini(monkeypatch, tmp_path):
    calls = []

    class FakeClient:
        def __init__(self, api_key):
            self.models = self

        def generate_content(self, model, contents, config):
            calls.append({"model": model, "config": config})

            class R:
                text = json.dumps(calls[-1].get("payload", FAKE["payload"]))
            return R()

    FAKE = {"payload": CANDS}
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    monkeypatch.setattr(cs.genai, "Client", FakeClient)
    monkeypatch.setattr(cs, "fetch_google_1t_tokens", lambda w: {"precursors": [], "followers": []})
    monkeypatch.setattr(cs, "fetch_google_books_ngram_frequencies", lambda c: {})
    monkeypatch.setattr(cs, "LLM_CACHE_PATH", tmp_path / "llm_cache.db")
    return calls, FAKE


def test_collocations_use_lite_model_without_thinking(gemini):
    calls, _ = gemini
    cs.CorpusService.get_collocations("lurk")
    assert calls[0]["model"] == "gemini-2.5-flash-lite"
    assert calls[0]["config"].thinking_config.thinking_budget == 0


def test_collocations_are_cached_per_word(gemini):
    calls, _ = gemini
    a = cs.CorpusService.get_collocations("lurk")
    b = cs.CorpusService.get_collocations("lurk")
    assert len(calls) == 1
    assert [c.chunk for c in b.candidates] == [c.chunk for c in a.candidates] == ["lurk in the shadows"]
    assert b.cached is True and a.cached is False


def test_refresh_bypasses_cache_and_empty_result_is_not_cached(gemini):
    calls, fake = gemini
    fake["payload"] = {"candidates": []}
    cs.CorpusService.get_collocations("dusk")
    fake["payload"] = CANDS
    cs.CorpusService.get_collocations("dusk")  # 빈 결과는 캐시하지 않았으므로 다시 호출
    cs.CorpusService.get_collocations("dusk", refresh=True)
    assert len(calls) == 3


# ---- Leech 목록 캐시 ------------------------------------------------------
@pytest.fixture
def leech_anki(monkeypatch, tmp_path):
    monkeypatch.setattr(link_manager, "DB_PATH", tmp_path / "links.db")
    init_db()
    LinkManager.invalidate_leech_cache()
    calls = []

    def invoke(action, **p):
        calls.append(action)
        if action == "findCards":
            return [1, 2, 3]
        if action == "cardsInfo":
            return [{"cardId": c, "note": c * 10, "lapses": c, "factor": 1300, "reps": 1,
                     "fields": {"단어": {"value": f"w{c}"}, "뜻": {"value": ""}, "품사": {"value": ""}}} for c in p["cards"]]
        raise AssertionError(action)

    monkeypatch.setattr(AnkiConnector, "invoke", staticmethod(invoke))
    return calls


def test_leech_pages_reuse_one_anki_fetch(leech_anki):
    p1 = LinkManager.get_vocab_list(limit=2, offset=0, filter_mode="leech")
    p2 = LinkManager.get_vocab_list(limit=2, offset=2, filter_mode="leech")
    assert leech_anki.count("cardsInfo") == 1
    assert [i["note_id"] for i in p1["items"]] == [30, 20] and [i["note_id"] for i in p2["items"]] == [10]


def test_leech_cache_invalidation_refetches(leech_anki):
    LinkManager.get_vocab_list(limit=2, offset=0, filter_mode="leech")
    LinkManager.invalidate_leech_cache()
    LinkManager.get_vocab_list(limit=2, offset=0, filter_mode="leech")
    assert leech_anki.count("cardsInfo") == 2


def test_leech_apply_invalidates_cache(monkeypatch):
    from backend.services import leech_service
    called = []
    monkeypatch.setattr(LinkManager, "invalidate_leech_cache", classmethod(lambda cls: called.append(1)))
    monkeypatch.setattr(AnkiConnector, "invoke", staticmethod(lambda a, **p: []))
    leech_service.apply_actions([{"note_id": 1, "word": "x", "meaning": "", "action": "skip"}])
    assert called


# ---- 정규식 캐시 ------------------------------------------------------------
def test_build_regex_compiles_each_word_once(monkeypatch):
    # re 모듈 자체 캐시는 512개뿐이다. 단어가 8천 개면 매번 다시 컴파일된다.
    import re as real_re
    count = {"n": 0}
    orig = real_re.compile

    def counting(*a, **k):
        count["n"] += 1
        return orig(*a, **k)

    monkeypatch.setattr(link_manager.re, "compile", counting)
    PatternMatcher.clear_regex_cache()
    words = [f"wordx{i}" for i in range(600)]
    for _ in range(2):
        for w in words:
            PatternMatcher.build_regex(w)
    assert count["n"] == 600
