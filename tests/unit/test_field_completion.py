"""빈 필드 채우기: AI 응답은 누락된 필드에만 써야 하고, 노트 하나의 실패가 전체를 멈추면 안 된다."""
import pytest

from core import completer as completer_mod
from integrations.anki_connect import AnkiConnector

CALLS: dict = {}  # 가짜 Gemini 호출 기록 (env fixture가 채운다)


def _vocab(nid, word, **fields):
    base = {"단어": word, "뜻": "", "품사": "v", "유의어": "", "예문": "", "사진": "", "설명": "", "소리": ""}
    base.update(fields)
    return {"noteId": nid, "modelName": "English Vocabulary", "fields": {k: {"value": v} for k, v in base.items()}}


@pytest.fixture
def env(monkeypatch):
    notes = {"English Vocabulary": [], "English Sentence": [], "English Grammar": []}
    updates = []
    responses = {}

    def find_notes(query):
        for model, ns in notes.items():
            if f'note:"{model}"' in query:
                return [n["noteId"] for n in ns]
        return []

    def notes_info(ids):
        return [n for ns in notes.values() for n in ns if n["noteId"] in ids]

    monkeypatch.setattr(AnkiConnector, "find_notes", classmethod(lambda cls, q: find_notes(q)))
    monkeypatch.setattr(AnkiConnector, "get_notes_info", classmethod(lambda cls, ids: notes_info(ids)))
    monkeypatch.setattr(AnkiConnector, "update_note_fields", classmethod(lambda cls, nid, f: updates.append((nid, f))))

    calls = {"batch": [], "single": []}

    class FakeCompleter:
        def __init__(self, pbar=None):
            pass

        def complete_fields(self, model, main_val, current, missing):
            calls["single"].append(main_val)
            r = responses[main_val]
            if isinstance(r, Exception):
                raise r
            return r

        def complete_fields_batch(self, model, notes):
            calls["batch"].append([n["main"] for n in notes])
            if responses.get("__batch_error__"):
                raise RuntimeError("batch failed")
            out = {}
            for n in notes:
                r = responses[n["main"]]
                if isinstance(r, Exception):
                    raise r
                if n["main"] in responses.get("__omit__", ()):
                    continue
                out[n["id"]] = r
            return out

    monkeypatch.setattr(completer_mod, "NoteCompleter", FakeCompleter)
    global CALLS
    CALLS = calls
    return notes, updates, responses


def test_ai_response_only_fills_missing_fields(env):
    notes, updates, responses = env
    notes["English Vocabulary"].append(_vocab(1, "run", 뜻="", 예문="", 설명=""))
    responses["run"] = {"단어": "RUN (changed)", "품사": "n", "뜻": "달리다", "예문": "I run.", "설명": "d", "unknown": "x"}
    completer_mod.run_universal_field_completion()
    assert updates == [(1, {"뜻": "달리다", "예문": "I run.", "설명": "d"})]


def test_non_string_values_are_dropped(env):
    notes, updates, responses = env
    notes["English Vocabulary"].append(_vocab(1, "run"))
    responses["run"] = {"뜻": ["달리다", "뛰다"], "예문": "I run.", "설명": None}
    completer_mod.run_universal_field_completion()
    assert updates == [(1, {"예문": "I run."})]


def test_one_failure_does_not_stop_others(env):
    notes, updates, responses = env
    notes["English Vocabulary"] += [_vocab(1, "run"), _vocab(2, "walk")]
    responses["run"] = RuntimeError("gemini 500")
    responses["walk"] = {"뜻": "걷다", "예문": "I walk.", "설명": "d"}
    completer_mod.run_universal_field_completion()
    assert (2, {"뜻": "걷다", "예문": "I walk.", "설명": "d"}) in updates


def _ok(word):
    return {"뜻": f"뜻-{word}", "예문": f"ex {word}", "설명": "d"}


def test_notes_are_sent_ten_per_call(env):
    notes, updates, responses = env
    for i in range(23):
        notes["English Vocabulary"].append(_vocab(i + 1, f"w{i}"))
        responses[f"w{i}"] = _ok(f"w{i}")
    completer_mod.run_universal_field_completion()
    assert [len(b) for b in CALLS["batch"]] == [10, 10, 3]
    assert CALLS["single"] == []
    assert len(updates) == 23


def test_note_missing_from_batch_answer_is_retried_alone(env):
    notes, updates, responses = env
    notes["English Vocabulary"] += [_vocab(1, "run"), _vocab(2, "walk")]
    responses.update({"run": _ok("run"), "walk": _ok("walk"), "__omit__": {"walk"}})
    completer_mod.run_universal_field_completion()
    assert CALLS["single"] == ["walk"]
    assert {nid for nid, _ in updates} == {1, 2}


def test_failed_batch_falls_back_to_single_calls(env):
    notes, updates, responses = env
    notes["English Vocabulary"] += [_vocab(1, "run"), _vocab(2, "walk")]
    responses.update({"run": _ok("run"), "walk": _ok("walk"), "__batch_error__": True})
    completer_mod.run_universal_field_completion()
    assert sorted(CALLS["single"]) == ["run", "walk"]
    assert {nid for nid, _ in updates} == {1, 2}
