"""아침 브리핑·저녁 리마인더 (텔레그램 Anki 봇). 백엔드 통계 API와 전송·동기화는 가짜로 바꿔 끼운다."""
import datetime

import pytest

from integrations import daily_brief as b

TODAY = datetime.date(2026, 10, 12)


def _overview(reviews_today=0, due_remaining=233, yesterday_reviews=412, streak=20):
    return {
        "today": {"date": TODAY.isoformat(), "reviews": reviews_today, "minutes": 0.0,
                  "due_remaining": due_remaining, "due_tomorrow": 287, "new_available": 266},
        "habit": {"current": streak, "longest": 133},
        "retention_30d": {"all": {"reviews": 8609, "passed": 7491, "rate": 87.0}},
        "heatmap": [{"date": "2026-10-10", "reviews": 300, "minutes": 40.0},
                    {"date": "2026-10-11", "reviews": yesterday_reviews, "minutes": 51.5}],
    }


class Calls:
    def __init__(self, overview=None, fetch_exc=None, sync_exc=None):
        self.sent, self.order = [], []
        self.overview, self.fetch_exc, self.sync_exc = overview, fetch_exc, sync_exc

    def fetch(self):
        self.order.append("fetch")
        if self.fetch_exc:
            raise self.fetch_exc
        return self.overview

    def sync(self):
        self.order.append("sync")
        if self.sync_exc:
            raise self.sync_exc

    def send(self, text):
        self.sent.append(text)

    def run(self, kind):
        b.run(kind, fetch=self.fetch, sync=self.sync, send=self.send)


def test_morning_brief_contents():
    msg = b.format_morning(_overview())
    for part in ["233", "266", "412", "52분", "20일", "87.0%"]:
        assert part in msg, part


def test_morning_brief_without_yesterday_in_heatmap():
    ov = _overview()
    ov["heatmap"] = ov["heatmap"][:1]
    assert "어제 0장" in b.format_morning(ov)


def test_evening_reminds_only_when_nothing_reviewed():
    msg = b.format_evening(_overview(reviews_today=0))
    assert "233" in msg and "20일" in msg and "동기화" in msg
    assert b.format_evening(_overview(reviews_today=5)) is None


def test_run_syncs_before_reading_stats():
    c = Calls(_overview())
    c.run("morning")
    assert c.order == ["sync", "fetch"]
    assert len(c.sent) == 1


def test_evening_after_review_sends_nothing():
    c = Calls(_overview(reviews_today=40))
    c.run("evening")
    assert c.sent == []


def test_sync_failure_still_sends_brief():
    c = Calls(_overview(), sync_exc=RuntimeError("network"))
    c.run("morning")
    assert len(c.sent) == 1 and "233" in c.sent[0]


def test_backend_failure_is_reported():
    c = Calls(fetch_exc=RuntimeError("connection refused"))
    c.run("morning")
    assert len(c.sent) == 1 and "실패" in c.sent[0]


def test_unknown_kind_rejected():
    with pytest.raises(ValueError):
        b.run("noon", fetch=lambda: {}, sync=lambda: None, send=lambda t: None)
