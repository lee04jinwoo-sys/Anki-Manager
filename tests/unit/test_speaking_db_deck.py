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


def test_next_question_marks_answered_done_and_skips_unanswered(tmp_path):
    store = SpeakingStore(tmp_path / "s.db")
    svc = SpeakingService(store=store, anki_deck=DbQuestionDeck(store, QS), today_fn=lambda: dt.date(2026, 11, 19))

    first = svc.start_or_resume_today()
    assert first["message"] == "Question 1?"

    skipped = svc.next_question()  # 답 없이 /next -> 건너뛰기
    assert skipped["message"] == "Question 2?" or "Question 2?" in skipped["message"]
    assert svc.store.question_statuses().get("daily_001") == "open"  # 건너뛴 질문은 닫히지 않음

    store.save_card_attempt(
        session_date="2026-11-19", card_id=2, note_id=2, topic_id="daily_002", prompt_text="Question 2?",
        attempt_num=1, mode="card", transcript="t", audio_path=None,
        metrics=__import__("speaking.models", fromlist=["SpeakingMetrics"]).SpeakingMetrics(),
        feedback={}, score=7.0,
    )
    nxt = svc.next_question()  # 답한 뒤 /next -> 완료 처리 후 다음 질문
    assert store.question_statuses().get("daily_002") == "done"
    assert nxt["status"] == "next_card"
    assert store.count_rated_today("2026-11-19") == 1
    assert store.compute_streaks(today=dt.date(2026, 11, 19))["current"] == 1
