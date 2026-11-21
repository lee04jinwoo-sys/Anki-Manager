"""speaking.service v2 단위 테스트: Anki 질문 카드 큐, 재녹음, FSRS 즉시 평가, 하루 요약, 녹음 보관."""
import datetime as dt

from speaking.models import (
    CardCandidate,
    CardEvaluation,
    QueueCounts,
    SpeakingCard,
    SpeakingMetrics,
    TranscriptionResult,
)
from speaking.service import SpeakingService
from speaking.store import SpeakingStore


class FakeSTT:
    def __init__(self):
        self.calls = []

    def transcribe(self, audio_bytes: bytes, filename: str = "voice.ogg", language="en") -> TranscriptionResult:
        self.calls.append((audio_bytes, language))
        idx = len(self.calls)
        # 2번째 호출(재녹음)에서는 WPM 상승·필러 감소
        if idx == 2:
            m = SpeakingMetrics(duration_sec=45.0, word_count=96, wpm=128.0, filler_count=1, long_pause_count=0, max_pause_sec=0.5)
            return TranscriptionResult(transcript="I study engineering science focusing on ML.", metrics=m)
        m = SpeakingMetrics(duration_sec=60.0, word_count=95, wpm=95.0, filler_count=5, long_pause_count=2, max_pause_sec=1.9)
        return TranscriptionResult(transcript=f"Spoken answer #{idx}.", metrics=m)


class FakeCoach:
    def evaluate_card(self, card, transcript, metrics, prior_history=()):
        return CardEvaluation(
            score=6.8,
            recommended_ease=2,
            summary="전반적 내용 명확하나 초반 필러가 있음.",
            corrections=["my major is about -> I major in"],
            native_model="I major in engineering science with a focus on machine learning.",
            card_candidates=[
                CardCandidate(
                    kind="sentence",
                    text="I major in engineering science.",
                    translation="저는 공학과학을 전공합니다.",
                    reason="자연스러운 전공 소개",
                ),
            ],
        )

    def evaluate_retry(self, card, first_transcript, first_metrics, retry_transcript, retry_metrics):
        return CardEvaluation(
            score=8.2,
            recommended_ease=3,
            summary="재녹음에서 필러가 줄고 훨씬 매끄러워짐.",
            corrections=[],
            native_model="I study engineering science focusing on ML.",
            card_candidates=[],
        )

    def analyze_debrief(self, transcript):
        return CardEvaluation(
            score=7.0,
            recommended_ease=3,
            summary="외부 대화에서 쓸 만한 정중한 요청 표현.",
            corrections=[],
            native_model="Would it be alright if I submitted this tomorrow?",
            card_candidates=[
                CardCandidate(
                    kind="vocab",
                    text="ask for an extension",
                    translation="기한 연장을 요청하다",
                    reason="외부 대화 회수",
                ),
            ],
        )


class FakeAnkiDeck:
    def __init__(self, initial_cards):
        self.cards = list(initial_cards)
        self.answered = []
        self.back_updates = []

    def get_deck_counts(self):
        new_c = sum(1 for c in self.cards if c.is_new)
        rev_c = sum(1 for c in self.cards if not c.is_new)
        return QueueCounts(new_count=new_c, learn_count=0, review_count=rev_c, total_in_deck=72)

    def fetch_today_queue(self):
        return self.get_deck_counts(), list(self.cards)

    def answer_speaking_card(self, card_id, ease):
        self.answered.append((card_id, ease))
        self.cards = [c for c in self.cards if c.card_id != card_id]

    def update_card_back_log(self, note_id, history):
        self.back_updates.append((note_id, history))


def test_v2_queue_retry_rate_summary_and_audio_archive(tmp_path):
    store = SpeakingStore(tmp_path / "speaking.db")
    audio_dir = tmp_path / "audio_archive"
    # 101번 카드에 과거 기록 1건 삽입 -> 복습 시 직전 힌트 출력 확인
    store.save_card_attempt(
        session_date="2026-11-16",
        card_id=101,
        note_id=501,
        topic_id="daily_001",
        prompt_text="Explain your major.",
        attempt_num=1,
        mode="card",
        transcript="old",
        audio_path=None,
        metrics=SpeakingMetrics(duration_sec=50, word_count=80, wpm=96.0, filler_count=4),
        feedback={"native_model": "I major in engineering."},
        score=6.5,
    )
    store.mark_attempt_rated(1, ease=2)

    cards = [
        SpeakingCard(card_id=101, note_id=501, topic_id="daily_001", category="Campus", title="Major", prompt_text="Explain your major.", is_new=False, reps=1),
        SpeakingCard(card_id=202, note_id=502, topic_id="daily_010", category="Toronto", title="TTC", prompt_text="Describe a TTC commute.", is_new=True, reps=0),
    ]
    deck = FakeAnkiDeck(cards)
    synced = []
    added_cards = []

    svc = SpeakingService(
        store=store,
        anki_deck=deck,
        stt=FakeSTT(),
        coach=FakeCoach(),
        tts_fn=lambda text: b"TTS-OGG",
        audio_dir=audio_dir,
        card_creator=lambda kind, payload: (added_cards.append((kind, payload)) or {"success": True, "note_id": 991, "duplicate": False}),
        on_anki_changed=lambda: synced.append(1),
        today_fn=lambda: dt.date(2026, 11, 19),
    )

    # 1) 아침/수동 큐 시작: 진행 표시 1/2와 질문만, 직전 기록 힌트 포함
    s = svc.start_or_resume_today()
    assert s["status"] == "question"
    assert s["message"].startswith("1/2")
    assert "새 카드" not in s["message"]
    assert "I major in engineering." in s["message"]

    # 2) 카드 101 1차 녹음 -> 저장, answerCards는 아직 미호출
    v1 = svc.submit_voice(b"RAW-1", filename="v1.ogg")
    assert v1["status"] == "evaluated"
    assert v1["recommended_ease"] == 2
    assert v1["audio_bytes"] == b"TTS-OGG"
    assert deck.answered == []
    saved_files = list((audio_dir / "2026-11-19").glob("card_101_*.ogg"))
    assert len(saved_files) == 1

    # 3) 재녹음 요청 + 2차 녹음 -> WPM 델타 포함
    retry_prompt = svc.request_retry()
    assert "재녹음" in retry_prompt["message"]
    v2 = svc.submit_voice(b"RAW-2", filename="v2.ogg")
    assert v2["recommended_ease"] == 3
    assert "95 -> 128" in v2["message"] or "95→128" in v2["message"]

    # 4) Good(3) 평가 -> Anki answerCards 호출, 뒷면 로그 갱신, 다음 카드 [2/2] 출제
    r1 = svc.rate_current_card(101, 3)
    assert deck.answered == [(101, 3)]
    assert len(deck.back_updates) == 1
    assert len(synced) == 1
    assert r1["status"] == "next_card"
    assert "2/2" in r1["message"]
    assert "TTC" in r1["message"]

    # 5) 카드 202 녹음 후 Easy(4) 평가 -> 0장 남음 -> 하루 요약 + 후보 버튼 반환
    svc.submit_voice(b"RAW-3", filename="v3.ogg")
    r2 = svc.rate_current_card(202, 4)
    assert r2["status"] == "day_completed"
    assert len(r2["candidates"]) == 1
    assert "완료" in r2["message"]
    assert store.compute_streaks(today=dt.date(2026, 11, 19))["current"] == 1

    # 6) 후보 등록 버튼 -> speaking 태그
    reg = svc.register_candidate(r2["candidates"][0]["id"])
    assert reg["success"] is True
    assert added_cards[0][1]["tags"] == ["speaking"]

    # 7) 오늘 0장 상태에서 음성 -> 외부 대화 회수 모드 (answerCards 미호출)
    debrief = svc.submit_voice(b"RAW-DEBRIEF", filename="d.ogg")
    assert debrief["mode"] == "debrief"
    assert len(deck.answered) == 2
    assert len(debrief["candidates"]) == 1


def test_back_log_failure_does_not_block_anki_rating(tmp_path):
    store = SpeakingStore(tmp_path / "speaking.db")
    cards = [SpeakingCard(card_id=101, note_id=501, topic_id="daily_001", prompt_text="Q1", is_new=True)]
    deck = FakeAnkiDeck(cards)

    def broken_back_log(note_id, history):
        raise RuntimeError("Anki updateNoteFields failed")

    deck.update_card_back_log = broken_back_log
    svc = SpeakingService(
        store=store,
        anki_deck=deck,
        stt=FakeSTT(),
        coach=FakeCoach(),
        tts_fn=lambda text: None,
        audio_dir=tmp_path / "audio",
        today_fn=lambda: dt.date(2026, 11, 19),
    )
    svc.start_or_resume_today()
    svc.submit_voice(b"RAW")
    out = svc.rate_current_card(101, 3)

    assert out["status"] == "day_completed"
    assert deck.answered == [(101, 3)]


def test_duplicate_rating_is_ignored(tmp_path):
    store = SpeakingStore(tmp_path / "speaking.db")
    cards = [SpeakingCard(card_id=101, note_id=501, topic_id="daily_001", prompt_text="Q1", is_new=True)]
    deck = FakeAnkiDeck(cards)
    svc = SpeakingService(
        store=store,
        anki_deck=deck,
        stt=FakeSTT(),
        coach=FakeCoach(),
        tts_fn=lambda text: None,
        audio_dir=tmp_path / "audio",
        today_fn=lambda: dt.date(2026, 11, 19),
    )
    svc.start_or_resume_today()
    svc.submit_voice(b"RAW")
    svc.rate_current_card(101, 3)
    again = svc.rate_current_card(101, 3)

    assert again["status"] == "already_rated"
    assert deck.answered == [(101, 3)]
