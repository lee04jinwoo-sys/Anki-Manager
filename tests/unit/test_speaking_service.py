"""speaking.service 단위 테스트: 3단계 전체 세션 흐름(1->0 트래커 연동) + 외부 회수 + 버튼 카드 등록."""
import datetime as dt

import pytest

from speaking.models import (
    CardCandidate,
    CoachFeedback,
    SpeakingMetrics,
    TranscriptionResult,
)
from speaking.service import SpeakingService
from speaking.store import SpeakingStore


class FakeSTT:
    def __init__(self):
        self.calls = 0

    def transcribe(self, audio_bytes: bytes, filename: str = "voice.ogg") -> TranscriptionResult:
        self.calls += 1
        # 2차 압축에서 WPM 상승·필러 감소 시뮬레이션
        if self.calls == 4:
            metrics = SpeakingMetrics(duration_sec=56.0, word_count=125, wpm=133.9, filler_count=1, long_pause_count=0, max_pause_sec=0.8)
            return TranscriptionResult(transcript="Compressed fluent pass 2 answer.", metrics=metrics)
        metrics = SpeakingMetrics(duration_sec=80.0, word_count=130, wpm=97.5, filler_count=5, long_pause_count=2, max_pause_sec=2.1)
        return TranscriptionResult(transcript=f"Spoken answer #{self.calls}.", metrics=metrics)


class FakeCoach:
    def evaluate_warmup(self, prompt, transcript, metrics):
        return CoachFeedback(
            summary="워밍업 자연스러움.",
            score=7.5,
            corrections=[],
            native_model="I usually grab coffee before class.",
            followup_question=None,
            card_candidates=[],
        )

    def evaluate_main_pass1(self, prompt, track, mission_vocab, transcript, metrics):
        return CoachFeedback(
            summary="논지는 명확하나 초반 멈춤이 2회 있음.",
            score=6.5,
            corrections=["make a bottleneck -> create a bottleneck"],
            native_model="We hit a severe bottleneck, so we redesigned the pipeline.",
            followup_question=None,
            card_candidates=[
                CardCandidate(
                    kind="sentence",
                    text="We hit a severe bottleneck, so we redesigned the pipeline.",
                    translation="심각한 병목에 부딪혀서 파이프라인을 재설계했다.",
                    reason="병목 표현 자연화",
                ),
            ],
        )

    def evaluate_main_pass2(self, prompt, track, pass1_transcript, pass1_metrics, pass2_transcript, pass2_metrics):
        return CoachFeedback(
            summary="2차에서 필러가 5→1로 줄고 말속도가 크게 개선됨.",
            score=7.8,
            corrections=[],
            native_model="Redesigned the pipeline to eliminate the bottleneck.",
            followup_question="What trade-off did you accept when redesigning it?",
            card_candidates=[],
        )

    def evaluate_followup(self, followup_question, transcript, metrics):
        return CoachFeedback(
            summary="즉흥 대응 안정적.",
            score=7.2,
            corrections=["similar with -> similar to"],
            native_model="The trade-off was similar to what we saw earlier.",
            followup_question=None,
            card_candidates=[
                CardCandidate(
                    kind="grammar",
                    text="The trade-off was similar to what we saw earlier.",
                    translation="그 타협은 앞서 본 것과 유사했다.",
                    answer="to",
                    distractors=["with"],
                    reason="전치사 오류",
                ),
            ],
        )

    def analyze_debrief(self, transcript):
        return CoachFeedback(
            summary="카페에서 연장 요청할 때 자연스러운 표현 2개 추출.",
            score=None,
            corrections=[],
            native_model="Could I get an extra day to polish this?",
            followup_question=None,
            card_candidates=[
                CardCandidate(
                    kind="vocab",
                    text="polish up",
                    translation="다듬다, 마무리하다",
                    reason="외부 대화 회수",
                ),
            ],
        )


class FakeTracker:
    def __init__(self):
        self.done_calls = 0
        self.reset_calls = 0

    def reset_daily(self):
        self.reset_calls += 1
        return {"card_id": 6001, "due_days": "0"}

    def mark_done(self):
        self.done_calls += 1
        return {"card_id": 6001, "due_days": "1"}


def test_full_three_step_session_marks_single_anki_tracker_done(tmp_path):
    store = SpeakingStore(tmp_path / "speaking.db")
    tracker = FakeTracker()
    added_cards = []
    synced = []

    def fake_add_card(kind, payload):
        added_cards.append((kind, payload))
        return {"success": True, "note_id": 900 + len(added_cards), "duplicate": False}

    svc = SpeakingService(
        store=store,
        stt=FakeSTT(),
        coach=FakeCoach(),
        tracker=tracker,
        tts_fn=lambda text: b"AUDIO-" + text[:10].encode(),
        vocab_fetcher=lambda count: [{"word": "bottleneck", "meaning": "병목"}],
        card_creator=fake_add_card,
        on_anki_changed=lambda: synced.append(1),
        today_fn=lambda: dt.date(2026, 11, 18),
    )

    # 0) 세션 시작
    start = svc.start_session(track="interview")
    assert start["step"] == "warmup_1"
    assert "워밍업" in start["message"]
    assert tracker.done_calls == 0

    # 1) 워밍업 1 -> 워밍업 2
    r1 = svc.handle_voice(b"a1")
    assert r1["step"] == "warmup_2"
    assert tracker.done_calls == 0

    # 2) 워밍업 2 -> 메인 1차
    r2 = svc.handle_voice(b"a2")
    assert r2["step"] == "main_pass1"
    assert "bottleneck" in r2["message"]
    assert tracker.done_calls == 0

    # 3) 메인 1차 -> 메인 2차 (압축 재발화) + 원어민 TTS 음성 첨부
    r3 = svc.handle_voice(b"a3")
    assert r3["step"] == "main_pass2"
    assert r3["audio_bytes"] is not None
    assert "WPM" in r3["message"]
    assert tracker.done_calls == 0

    # 4) 메인 2차 -> 꼬리질문 (1차 대비 delta 포함)
    r4 = svc.handle_voice(b"a4")
    assert r4["step"] == "followup"
    assert "What trade-off did you accept" in r4["message"]
    assert tracker.done_calls == 0

    # 5) 꼬리질문 완료 -> 세션 완료 + Anki 트래커 1 -> 0 + 후보 버튼 반환
    r5 = svc.handle_voice(b"a5")
    assert r5["step"] == "completed"
    assert tracker.done_calls == 1
    assert len(synced) == 1
    assert len(r5["candidates"]) == 2
    assert store.compute_streaks(today=dt.date(2026, 11, 18))["current"] == 1

    # 6) 사용자가 후보 버튼 클릭 -> speaking 태그로 Anki 등록
    first_cid = r5["candidates"][0]["id"]
    reg = svc.register_candidate(first_cid)
    assert reg["success"] is True
    assert added_cards[0][0] == "sentence"
    assert "speaking" in added_cards[0][1]["tags"]
    assert len(synced) == 2

    # 중복 클릭 시 이미 등록됨 반환
    dup = svc.register_candidate(first_cid)
    assert dup["already_added"] is True
    assert len(added_cards) == 1


def test_voice_without_active_session_runs_debrief_mode(tmp_path):
    store = SpeakingStore(tmp_path / "speaking.db")
    tracker = FakeTracker()
    svc = SpeakingService(
        store=store,
        stt=FakeSTT(),
        coach=FakeCoach(),
        tracker=tracker,
        tts_fn=lambda text: b"OGG",
        vocab_fetcher=lambda count: [],
        card_creator=lambda kind, payload: {"success": True, "note_id": 777},
        today_fn=lambda: dt.date(2026, 11, 18),
    )

    res = svc.handle_voice(b"debrief-audio")
    assert res["mode"] == "debrief"
    assert len(res["candidates"]) == 1
    assert res["candidates"][0]["kind"] == "vocab"
    assert tracker.done_calls == 0  # 외부 회수는 일일 스피킹 완료로 치지 않음
