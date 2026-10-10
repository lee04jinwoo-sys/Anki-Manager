"""Obsidian Inbox 커밋: Anki에 실제로 들어간 항목만 Inbox에서 지워야 한다."""
import time

import pytest

from backend.schemas.importer import ObsidianCommitRequest, VocabItem
from backend.services import importer_service, maintenance_service
from backend.services.jobs import jobs
from collectors.obsidian import ObsidianManager

INBOX = """## Sentences
- I ran into an old friend.
- She turned down the offer.

## Vocab
- spring sth on sb
- reluctant
"""


@pytest.fixture
def inbox(tmp_path, monkeypatch):
    path = tmp_path / "Inbox.md"
    path.write_text(INBOX, encoding="utf-8")

    class TmpManager(ObsidianManager):
        def __init__(self):
            super().__init__()
            self.file_path = str(path)

    monkeypatch.setattr(importer_service, "ObsidianManager", TmpManager)
    monkeypatch.setattr(maintenance_service, "run_steps_blocking", lambda *a, **k: None)
    jobs.reset()
    return path


def _commit_and_wait(req):
    res = importer_service.start_commit(req)
    assert res.status == "success", res.message
    deadline = time.time() + 5
    while jobs.is_running and time.time() < deadline:
        time.sleep(0.01)
    assert not jobs.is_running


def _req():
    return ObsidianCommitRequest(
        selected_sentences=["I ran into an old friend.", "She turned down the offer."],
        selected_vocab=[VocabItem(word="spring sth on sb"), VocabItem(word="reluctant")],
    )


def test_nothing_added_keeps_inbox_intact(inbox, monkeypatch):
    # Gemini 실패 등으로 아무것도 등록되지 않은 경우
    monkeypatch.setattr(importer_service, "run_note_completion", lambda s, v: (True, [], []))
    _commit_and_wait(_req())
    assert inbox.read_text(encoding="utf-8") == INBOX


def test_only_processed_items_removed(inbox, monkeypatch):
    # 문장 1개, 단어 1개(플레이스홀더 정규화된 이름으로 반환)만 등록된 경우
    monkeypatch.setattr(
        importer_service,
        "run_note_completion",
        lambda s, v: (True, ["I ran into an old friend."], ["spring A on B"]),
    )
    _commit_and_wait(_req())
    text = inbox.read_text(encoding="utf-8")
    assert "I ran into an old friend." not in text
    assert "spring sth on sb" not in text
    assert "She turned down the offer." in text
    assert "reluctant" in text


def test_completion_exception_keeps_inbox(inbox, monkeypatch):
    def boom(s, v):
        raise RuntimeError("gemini down")

    monkeypatch.setattr(importer_service, "run_note_completion", boom)
    _commit_and_wait(_req())
    assert inbox.read_text(encoding="utf-8") == INBOX


def test_remove_does_not_wipe_non_ascii_lines(tmp_path):
    # 한글만 있는 줄은 영숫자 정규화 시 빈 문자열이 되어 서로 일치해버리면 안 된다.
    path = tmp_path / "Inbox.md"
    path.write_text("## Vocab\n- 사과\n- 바나나\n", encoding="utf-8")
    mgr = ObsidianManager()
    mgr.file_path = str(path)
    mgr.remove_processed_items([], ["사과"])
    text = path.read_text(encoding="utf-8")
    assert "바나나" in text
