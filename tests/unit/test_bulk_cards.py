"""일괄 등록: AnkiConnect addNotes는 하나라도 실패하면 전부 롤백한다. 중복 1개가 나머지를 막으면 안 된다."""
import pytest

from backend.schemas.cards import SentenceBulkCreateRequest, SentenceItem, VocabBulkCreateRequest, VocabItem
from backend.services import card_service
from integrations.anki_connect import AnkiConnector


class FakeAnki:
    """설치된 AnkiConnect(2055492159)의 addNotes/canAddNotes 동작을 흉내낸다."""

    def __init__(self, existing):
        self.existing = set(existing)
        self.next_id = 1000

    def _key(self, note):
        return next(iter(note["fields"].values()))

    def invoke(self, action, **params):
        if action == "canAddNotes":
            return [self._key(n) not in self.existing for n in params["notes"]]
        if action == "addNotes":
            notes = params["notes"]
            if any(self._key(n) in self.existing for n in notes):
                raise Exception("['cannot create note because it is a duplicate']")  # 전부 롤백
            ids = []
            for n in notes:
                self.existing.add(self._key(n))
                self.next_id += 1
                ids.append(self.next_id)
            return ids
        raise AssertionError(action)


@pytest.fixture
def anki(monkeypatch):
    queued = []
    monkeypatch.setattr(card_service, "queue_background_audio", lambda nid, text, is_sentence=True: queued.append(nid))
    monkeypatch.setattr(card_service.LinkManager, "index_single_sentence", classmethod(lambda cls, *a: None))
    monkeypatch.setattr(card_service.LinkManager, "index_single_vocab", classmethod(lambda cls, *a: None))

    def make(existing):
        f = FakeAnki(existing)
        monkeypatch.setattr(AnkiConnector, "invoke", staticmethod(f.invoke))
        return f, queued
    return make


def test_one_duplicate_does_not_block_other_sentences(anki):
    f, queued = anki({"Old one."})
    req = SentenceBulkCreateRequest(
        items=[SentenceItem(sentence="New one.", translation="a"),
               SentenceItem(sentence="Old one.", translation="b"),
               SentenceItem(sentence="Another.", translation="c")],
        auto_enrich=False, generate_audio=True)
    res = card_service.create_bulk_sentences(req)
    assert res.count == 2 and res.total == 3 and res.skipped == 1
    assert {"New one.", "Another."} <= f.existing
    assert len(queued) == 2


def test_one_duplicate_does_not_block_other_vocab(anki):
    f, _ = anki({"run"})
    req = VocabBulkCreateRequest(items=[VocabItem(word="run"), VocabItem(word="walk")], generate_audio=False)
    res = card_service.create_bulk_vocabs(req)
    assert res.count == 1 and res.skipped == 1
    assert "walk" in f.existing
