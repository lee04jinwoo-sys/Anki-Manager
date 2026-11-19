"""speaking.store 단위 테스트: 세션·시도·토픽 SRS·카드 후보·스트릭 영속화."""
import datetime as dt

import pytest

from speaking.models import CardCandidate, SpeakingMetrics
from speaking.store import SpeakingStore


@pytest.fixture
def store(tmp_path):
    return SpeakingStore(tmp_path / "speaking.db")


def test_session_lifecycle_and_streak(store):
    day1 = dt.date(2026, 11, 18)
    day2 = dt.date(2026, 11, 19)

    s1 = store.create_session(
        session_date=day1.isoformat(),
        track="interview",
        topic_id="int_01",
        topic_prompt="Tell me about a tough bug you solved.",
        warmup_prompts=["How was your morning?", "What did you eat today?"],
        mission_vocab=["bottleneck", "trade-off"],
    )
    assert s1.step == "warmup_1"
    assert s1.status == "active"

    # 아직 완료 전이므로 스트릭 0
    assert store.compute_streaks(today=day1) == {"current": 0, "longest": 0, "total_completed": 0}

    store.advance_step(s1.id, "followup")
    store.complete_session(s1.id)
    assert store.get_active_session() is None
    assert store.compute_streaks(today=day1) == {"current": 1, "longest": 1, "total_completed": 1}

    # 다음 날 연속 완료
    s2 = store.create_session(
        session_date=day2.isoformat(),
        track="daily",
        topic_id="day_01",
        topic_prompt="Describe your favorite spot in Toronto.",
        warmup_prompts=["Q1", "Q2"],
        mission_vocab=[],
    )
    store.complete_session(s2.id)
    assert store.compute_streaks(today=day2) == {"current": 2, "longest": 2, "total_completed": 2}


def test_topic_srs_reschedules_weak_topic_sooner(store):
    today = dt.date(2026, 11, 18)

    # 점수 낮음(<= 6) -> 3일 뒤 재출제
    due_weak = store.record_topic_outcome("int_01", score=5.5, today=today)
    assert due_weak == (today + dt.timedelta(days=3)).isoformat()

    # 두 번째에 점수 높음(>= 8) -> 14일 이상 뒤로 밀림
    due_strong = store.record_topic_outcome("int_01", score=8.5, today=today + dt.timedelta(days=3))
    assert dt.date.fromisoformat(due_strong) >= today + dt.timedelta(days=17)

    # 만기 도래 토픽 조회
    due_ids = store.get_due_topic_ids(today=today + dt.timedelta(days=3))
    assert "int_01" not in due_ids
    due_ids_later = store.get_due_topic_ids(today=today + dt.timedelta(days=30))
    assert "int_01" in due_ids_later


def test_attempts_and_recent_metrics_summary(store):
    s = store.create_session(
        session_date="2026-11-18",
        track="ielts",
        topic_id="ielts_01",
        topic_prompt="Describe a book you enjoyed.",
        warmup_prompts=["W1", "W2"],
        mission_vocab=["compelling"],
    )
    m1 = SpeakingMetrics(duration_sec=85.0, word_count=140, wpm=98.8, filler_count=6, long_pause_count=3, max_pause_sec=2.4)
    m2 = SpeakingMetrics(duration_sec=58.0, word_count=118, wpm=122.1, filler_count=2, long_pause_count=1, max_pause_sec=1.6)

    store.save_attempt(s.id, "main_pass1", "I uh really liked...", m1, {"score": 6.5})
    store.save_attempt(s.id, "main_pass2", "I found this book compelling...", m2, {"score": 7.5})

    pass1 = store.get_attempt(s.id, "main_pass1")
    assert pass1 is not None
    assert pass1["metrics"]["wpm"] == pytest.approx(98.8)

    summary = store.recent_metrics_summary(days=14, today=dt.date(2026, 11, 18))
    assert summary["attempts_count"] == 2
    assert summary["avg_wpm"] == pytest.approx((98.8 + 122.1) / 2, rel=1e-2)
    assert summary["avg_fillers"] == pytest.approx(4.0)


def test_card_candidate_persistence_and_mark_added(store):
    cid = store.save_candidate(
        session_id=None,
        candidate=CardCandidate(
            kind="sentence",
            text="That trade-off paid off in the long run.",
            translation="그 타협은 장기적으로 효과가 있었다.",
            reason="막힌 표현 대체",
        ),
    )
    row = store.get_candidate(cid)
    assert row is not None
    assert row["added_note_id"] is None
    assert row["candidate"]["kind"] == "sentence"

    store.mark_candidate_added(cid, note_id=987654321)
    updated = store.get_candidate(cid)
    assert updated["added_note_id"] == 987654321
