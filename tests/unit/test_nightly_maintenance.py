"""밤 정리 작업: 빈 필드·오디오·품사만, 대상이 많으면 필드 단계를 건너뛰고 알림, 결과가 있을 때만 알림."""
import pytest

from integrations import nightly_maintenance as nm


class Fake:
    def __init__(self, before, after, start_result=None, states=None):
        self.counts = [before, after]
        self.started = []
        self.sent = []
        self.synced = 0
        self.start_result = start_result or {"status": "success", "message": "started"}
        self.states = list(states or [{"is_running": True, "status": "running"},
                                      {"is_running": False, "status": "success", "logs": []}])

    def count(self):
        return self.counts.pop(0)

    def start(self, steps):
        self.started.append(steps)
        return self.start_result

    def state(self):
        return self.states.pop(0) if len(self.states) > 1 else self.states[0]

    def sync(self):
        self.synced += 1

    def run(self, **kw):
        nm.run(count=self.count, start=self.start, state=self.state, sync=self.sync,
               send=self.sent.append, sleep=lambda s: None, **kw)


ZERO = {"fields": 0, "audio": 0, "pos": 0}


def test_nothing_to_do_is_quiet_and_starts_nothing():
    f = Fake(ZERO, ZERO)
    f.run()
    assert f.started == [] and f.sent == []


def test_runs_only_safe_steps_and_reports_what_changed():
    f = Fake({"fields": 3, "audio": 5, "pos": 2}, {"fields": 0, "audio": 1, "pos": 0})
    f.run()
    assert f.started == [["fields", "audio", "pos"]]
    assert len(f.sent) == 1
    msg = f.sent[0]
    assert "빈 필드 3" in msg and "오디오 4" in msg and "품사 2" in msg
    assert "남음" in msg          # 오디오 1개가 남았다
    assert f.synced == 1


def test_only_steps_with_targets_are_run():
    f = Fake({"fields": 0, "audio": 2, "pos": 0}, ZERO)
    f.run()
    assert f.started == [["audio"]]


def test_too_many_empty_fields_skips_fields_step_and_alerts():
    f = Fake({"fields": 500, "audio": 1, "pos": 0}, {"fields": 500, "audio": 0, "pos": 0})
    f.run(field_cap=100)
    assert f.started == [["audio"]]
    assert any("500" in m and "건너뜀" in m for m in f.sent)


def test_busy_backend_alerts_and_does_not_wait():
    f = Fake({"fields": 1, "audio": 0, "pos": 0}, ZERO,
             start_result={"status": "error", "message": "다른 작업이 실행 중입니다"})
    f.run()
    assert len(f.sent) == 1 and "실행 중" in f.sent[0]
    assert f.synced == 0


def test_job_error_is_reported_with_last_logs():
    f = Fake({"fields": 1, "audio": 0, "pos": 0}, {"fields": 1, "audio": 0, "pos": 0},
             states=[{"is_running": False, "status": "error",
                      "logs": [{"message": "a"}, {"message": "Gemini 429"}]}])
    f.run()
    assert "실패" in f.sent[0] and "Gemini 429" in f.sent[0]


def test_timeout_is_reported():
    f = Fake({"fields": 1, "audio": 0, "pos": 0}, ZERO, states=[{"is_running": True, "status": "running"}])
    f.run(timeout_polls=3)
    assert "시간 초과" in f.sent[0]


# --- 중국어 링크 야간 재스캔: Anki에서 직접 넣은 중국어 카드도 다음 날 연결되게 한다 ---

def test_relink_chinese_scans_zh_and_stays_quiet_on_success():
    calls, sent = [], []
    nm.relink_chinese(scan=lambda lang: calls.append(lang) or {"success": True, "data": {"total_links": 10}},
                      send=sent.append)
    assert calls == ["zh"]
    assert sent == []


def test_relink_chinese_failure_sends_one_warning_and_does_not_raise():
    sent = []

    def boom(lang):
        raise RuntimeError("backend down")

    nm.relink_chinese(scan=boom, send=sent.append)
    assert len(sent) == 1 and "중국어" in sent[0] and "backend down" in sent[0]


def test_main_relinks_even_when_cleanup_fails(monkeypatch):
    from integrations import anki_sync
    order, sent = [], []
    monkeypatch.setattr(anki_sync, "telegram_notifier", lambda: sent.append)

    def failing_run(**kw):
        order.append("run")
        raise RuntimeError("cleanup broke")

    monkeypatch.setattr(nm, "run", failing_run)
    monkeypatch.setattr(nm, "relink_chinese", lambda scan, send: order.append("relink"))
    with pytest.raises(RuntimeError):
        nm.main()
    assert order == ["run", "relink"]
