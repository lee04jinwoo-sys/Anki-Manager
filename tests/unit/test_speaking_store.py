"""speaking.store v2 단위 테스트: 일일 큐, 카드별 시도/녹음 경로, 카드 히스토리, 후보, 스트릭."""
import datetime as dt

import pytest

from speaking.models import CardCandidate, SpeakingMetrics
from speaking.store import SpeakingStore


@pytest.fixture
def store(tmp_path):
    return SpeakingStore(tmp_path / "speaking.db")


def test_daily_queue_lifecycle_and_streak(store):
    d1 = dt.date(2026, 11, 19)
    d2 = dt.date(2026, 11, 20)

    q1 = store.upsert_daily_queue(d1.isoformat(), total_assigned=2, active_card_id=101)
    assert q1["status"] == "active"
    assert q1["completed_count"] == 0
    assert store.compute_streaks(today=d1)["current"] == 0

    store.set_queue_state(d1.isoformat(), active_card_id=102, increment_completed=True)
    store.set_queue_state(d1.isoformat(), active_card_id=None, increment_completed=True, status="completed")
    assert store.compute_streaks(today=d1) == {"current": 1, "longest": 1, "total_completed": 1}

    store.upsert_daily_queue(d2.isoformat(), total_assigned=1, active_card_id=103)
    store.set_queue_state(d2.isoformat(), active_card_id=None, increment_completed=True, status="completed")
    assert store.compute_streaks(today=d2) == {"current": 2, "longest": 2, "total_completed": 2}


def test_card_attempts_history_and_today_summary_metrics(store):
    m1 = SpeakingMetrics(duration_sec=62.0, word_count=110, wpm=106.5, filler_count=4, long_pause_count=2, max_pause_sec=1.9)
    m2 = SpeakingMetrics(duration_sec=50.0, word_count=108, wpm=129.6, filler_count=1, long_pause_count=0, max_pause_sec=0.7)

    a1 = store.save_card_attempt(
        session_date="2026-11-19",
        card_id=101,
        note_id=501,
        topic_id="daily_001",
        prompt_text="Explain your major.",
        attempt_num=1,
        mode="card",
        transcript="First try",
        audio_path="/tmp/audio/card_101_1.ogg",
        metrics=m1,
        feedback={"summary": "1차", "native_model": "I study engineering science."},
        score=6.5,
    )
    a2 = store.save_card_attempt(
        session_date="2026-11-19",
        card_id=101,
        note_id=501,
        topic_id="daily_001",
        prompt_text="Explain your major.",
        attempt_num=2,
        mode="card",
        transcript="Retry try",
        audio_path="/tmp/audio/card_101_2.ogg",
        metrics=m2,
        feedback={"summary": "2차", "native_model": "I major in engineering science with an AI focus."},
        score=8.0,
    )

    latest = store.get_latest_attempt_for_card_today("2026-11-19", 101)
    assert latest["id"] == a2
    assert latest["audio_path"] == "/tmp/audio/card_101_2.ogg"

    store.mark_attempt_rated(a2, ease=3)
    history = store.list_card_history(card_id=101, limit=5, rated_only=True)
    assert len(history) == 1
    assert history[0]["ease"] == 3
    assert history[0]["wpm"] == pytest.approx(129.6)
    assert "AI focus" in history[0]["native_model"]

    summary = store.recent_metrics_summary(days=14, today=dt.date(2026, 11, 19))
    assert summary["attempts_count"] == 2
    assert summary["avg_wpm"] == pytest.approx((106.5 + 129.6) / 2, rel=1e-2)
    assert a1 != a2


def test_today_candidates_and_mark_added(store):
    cid = store.save_candidate(
        session_date="2026-11-19",
        attempt_id=10,
        candidate=CardCandidate(
            kind="sentence",
            text="I major in engineering science.",
            translation="저는 공학과학을 전공합니다.",
            reason="자연스러운 전공 표현",
        ),
    )
    today_cands = store.list_today_candidates("2026-11-19")
    assert len(today_cands) == 1
    assert today_cands[0]["id"] == cid

    store.mark_candidate_added(cid, note_id=8888)
    row = store.get_candidate(cid)
    assert row["added_note_id"] == 8888
