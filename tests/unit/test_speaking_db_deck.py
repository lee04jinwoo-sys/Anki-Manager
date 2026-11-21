import datetime as dt

from speaking.db_deck import DbQuestionDeck
from speaking.models import DailyQuestion
from speaking.service import SpeakingService
from speaking.store import SpeakingStore

QS = [DailyQuestion(id=f"daily_{i:03d}", category="Campus", prompt=f"Question {i}?") for i in range(1, 6)]


def test_queue_starts_with_first_question_and_advances_when_done(tmp_path):
    deck = DbQuestionDeck(SpeakingStore(tmp_path / "s.db"), QS)

    counts, cards = deck.fetch_today_queue()
    assert [c.prompt_text for c in cards] == ["Question 1?", "Question 2?", "Question 3?"]
    assert cards[0].is_new and cards[0].topic_id == "daily_001"

    deck.answer_speaking_card(cards[0].card_id, 3)
    _, cards = deck.fetch_today_queue()
    assert cards[0].prompt_text == "Question 2?"


def test_unanswered_open_question_stays_first_and_bank_restarts_after_full_round(tmp_path):
    store = SpeakingStore(tmp_path / "s.db")
    deck = DbQuestionDeck(store, QS)

    _, cards = deck.fetch_today_queue()
    _, cards = deck.fetch_today_queue()  # 답하지 않으면 같은 질문이 계속 맨 앞
    assert cards[0].prompt_text == "Question 1?"

    for i in range(1, 6):
        deck.answer_speaking_card(i, 3)
    _, cards = deck.fetch_today_queue()  # 한 바퀴 끝 -> 처음부터
    assert cards[0].prompt_text == "Question 1?"


def _attempt(store, card_id, duration):
    from speaking.models import SpeakingMetrics

    return store.save_card_attempt(
        session_date="2026-11-19", card_id=card_id, note_id=card_id, topic_id=f"daily_{card_id:03d}",
        prompt_text=f"Question {card_id}?", attempt_num=1, mode="card", transcript="t", audio_path=None,
        metrics=SpeakingMetrics(duration_sec=duration), feedback={}, score=7.0,
    )


def test_next_requires_a_valid_answer_and_advances_after_one(tmp_path):
    store = SpeakingStore(tmp_path / "s.db")
    svc = SpeakingService(store=store, queue=DbQuestionDeck(store, QS), today_fn=lambda: dt.date(2026, 11, 19))

    assert svc.start_or_resume_today()["message"] == "Question 1?"

    blocked = svc.next_question()  # 답 없이 /next -> 넘어가지 않음
    assert blocked["status"] == "not_answered"
    assert svc.start_or_resume_today()["message"] == "Question 1?"

    _attempt(store, 1, 12.0)  # 30초 미만 기록이 남아 있어도 넘어가지 않음
    assert svc.next_question()["status"] == "not_answered"
    assert svc.rate_current_card(1, 3)["status"] == "not_answered"
    assert store.question_statuses().get("daily_001") == "open"

    _attempt(store, 1, 40.0)
    nxt = svc.next_question()
    assert store.question_statuses().get("daily_001") == "done"
    assert nxt["status"] == "next_card"
    assert nxt["message"] == "Question 2?"
    assert store.count_rated_today("2026-11-19") == 1
    assert store.compute_streaks(today=dt.date(2026, 11, 19))["current"] == 1


def test_skip_swaps_question_without_closing_it(tmp_path):
    store = SpeakingStore(tmp_path / "s.db")
    svc = SpeakingService(store=store, queue=DbQuestionDeck(store, QS), today_fn=lambda: dt.date(2026, 11, 19))
    svc.start_or_resume_today()
    assert "Question 2?" in svc.skip_current_card()["message"]
    assert store.question_statuses().get("daily_001") == "open"
