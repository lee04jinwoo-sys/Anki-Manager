"""서버 Anki 정기 동기화와 실패 알림.

AnkiConnect 호출과 텔레그램 전송은 가짜 함수로 바꿔 끼운다.
"""
from integrations import anki_sync


class Recorder:
    def __init__(self, exc=None):
        self.calls = 0
        self.exc = exc

    def __call__(self):
        self.calls += 1
        if self.exc:
            raise self.exc


def _run(tmp_path, sync, notified):
    return anki_sync.sync_and_report(sync, notified.append, tmp_path / "sync_state.json")


def test_success_sends_nothing(tmp_path):
    notified = []
    assert _run(tmp_path, Recorder(), notified) is True
    assert notified == []


def test_failure_notifies_once_until_recovery(tmp_path):
    notified = []
    failing = Recorder(Exception("AnkiConnect 에러: network"))

    assert _run(tmp_path, failing, notified) is False
    assert _run(tmp_path, failing, notified) is False   # 같은 실패가 이어지면 다시 알리지 않는다
    assert len(notified) == 1 and "network" in notified[0]

    assert _run(tmp_path, Recorder(), notified) is True
    assert len(notified) == 2 and "복구" in notified[1]


def test_full_sync_required_tells_user_to_choose_in_vnc(tmp_path):
    notified = []
    exc = Exception("AnkiConnect 에러: Sync status 2 not one of [0, 1] - see SyncCollectionResponse")

    _run(tmp_path, Recorder(exc), notified)

    assert "전체 동기화" in notified[0] and "VNC" in notified[0]


def test_new_kind_of_failure_is_notified_again(tmp_path):
    notified = []
    _run(tmp_path, Recorder(Exception("network")), notified)
    _run(tmp_path, Recorder(Exception("auth not configured")), notified)

    assert len(notified) == 2


def test_notify_failure_does_not_crash(tmp_path):
    def broken_notify(text):
        raise RuntimeError("telegram down")

    assert anki_sync.sync_and_report(Recorder(Exception("x")), broken_notify, tmp_path / "s.json") is False


def test_corrupt_state_file_is_treated_as_fresh(tmp_path):
    state = tmp_path / "sync_state.json"
    state.write_text("{not json")
    notified = []

    anki_sync.sync_and_report(Recorder(Exception("x")), notified.append, state)

    assert len(notified) == 1
