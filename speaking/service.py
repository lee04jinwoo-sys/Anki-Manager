"""Channel-agnostic speaking session orchestrator (reusable by Telegram & future Web UI)."""
from __future__ import annotations

import datetime as dt
import logging
from typing import Any, Callable, Dict, List, Optional
from zoneinfo import ZoneInfo

from speaking.coach import SpeakingCoach
from speaking.models import (
    CardCandidate,
    CoachFeedback,
    SessionState,
    SpeakingMetrics,
    TrackName,
)
from speaking.speech import GroqWhisperClient, synthesize_coaching_audio
from speaking.store import SpeakingStore
from speaking.topics import get_topic_by_id, pick_warmups, select_topic
from speaking.tracker import AnkiSpeakingTracker, fetch_mission_vocab

logger = logging.getLogger("speaking.service")

TORONTO_TZ = ZoneInfo("America/Toronto")
SPEAKING_CARD_TAG = "speaking"


def _toronto_today() -> dt.date:
    now = dt.datetime.now(TORONTO_TZ)
    # Anki 일자 경계(새벽 4시)와 동일하게 맞춘다
    return (now - dt.timedelta(hours=4)).date()


def _format_metrics(m: SpeakingMetrics) -> str:
    return (
        f"길이 {m.duration_sec:.0f}초 · {m.word_count}단어 · "
        f"{m.wpm:.0f} WPM · 필러 {m.filler_count}회 · "
        f"긴 침묵(>=1.5s) {m.long_pause_count}회"
    )


def _format_delta(p1: SpeakingMetrics, p2: SpeakingMetrics) -> str:
    dwpm = p2.wpm - p1.wpm
    dfill = p2.filler_count - p1.filler_count
    dpause = p2.long_pause_count - p1.long_pause_count
    return (
        f"1차 -> 2차 변화: WPM {p1.wpm:.0f} -> {p2.wpm:.0f} ({dwpm:+.0f}), "
        f"필러 {p1.filler_count} -> {p2.filler_count} ({dfill:+d}), "
        f"긴 침묵 {p1.long_pause_count} -> {p2.long_pause_count} ({dpause:+d})"
    )


def _format_corrections(corrections: List[str]) -> str:
    if not corrections:
        return ""
    return "\n".join(f"- {c}" for c in corrections)


def _default_card_creator(kind: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    from backend.schemas.cards import (
        GrammarCreateRequest,
        SentenceCreateRequest,
        VocabCreateRequest,
    )
    from backend.services import card_service

    if kind == "vocab":
        req = VocabCreateRequest(**payload)
        res = card_service.create_vocab_card(req)
    elif kind == "grammar":
        req = GrammarCreateRequest(**payload)
        res = card_service.create_grammar_card(req)
    else:
        req = SentenceCreateRequest(**payload)
        res = card_service.create_sentence_card(req)
    return res.model_dump()


class SpeakingService:
    def __init__(
        self,
        store: Optional[SpeakingStore] = None,
        stt: Optional[Any] = None,
        coach: Optional[Any] = None,
        tracker: Optional[Any] = None,
        tts_fn: Optional[Callable[[str], Optional[bytes]]] = None,
        vocab_fetcher: Optional[Callable[[int], List[Dict[str, str]]]] = None,
        card_creator: Optional[Callable[[str, Dict[str, Any]], Dict[str, Any]]] = None,
        on_anki_changed: Optional[Callable[[], None]] = None,
        today_fn: Optional[Callable[[], dt.date]] = None,
    ) -> None:
        self.store = store or SpeakingStore()
        self.stt = stt or GroqWhisperClient()
        self.coach = coach or SpeakingCoach()
        self.tracker = tracker or AnkiSpeakingTracker()
        self.tts_fn = tts_fn or synthesize_coaching_audio
        self.vocab_fetcher = vocab_fetcher or (lambda count: fetch_mission_vocab(count=count))
        self.card_creator = card_creator or _default_card_creator
        self.on_anki_changed = on_anki_changed
        self.today_fn = today_fn or _toronto_today

    def _notify_anki_changed(self) -> None:
        if not self.on_anki_changed:
            return
        try:
            self.on_anki_changed()
        except Exception as e:
            logger.warning("Post-Anki callback failed: %s", e)

    def _persist_candidates(
        self, session_id: Optional[int], candidates: List[CardCandidate]
    ) -> List[Dict[str, Any]]:
        saved = []
        for cand in candidates:
            cid = self.store.save_candidate(session_id, cand)
            saved.append({"id": cid, **cand.model_dump()})
        return saved

    def start_session(self, track: Optional[TrackName] = None) -> Dict[str, Any]:
        today = self.today_fn()
        due_ids = self.store.get_due_topic_ids(today=today)
        recent_ids = self.store.get_recent_topic_ids(limit=12)
        last_track = self.store.get_last_completed_track()
        topic = select_topic(
            track=track,
            due_topic_ids=due_ids,
            recent_topic_ids=recent_ids,
            last_track=last_track,
        )
        warmups = pick_warmups(count=2)
        vocab_items = self.vocab_fetcher(3)
        mission_vocab = [
            f"{v['word']} ({v['meaning']})" if v.get("meaning") else v["word"]
            for v in vocab_items
        ]
        session = self.store.create_session(
            session_date=today.isoformat(),
            track=topic.track,
            topic_id=topic.id,
            topic_prompt=topic.prompt,
            warmup_prompts=warmups,
            mission_vocab=mission_vocab,
        )
        srs_tag = " [SRS 복습 주제]" if topic.id in due_ids else ""
        msg = (
            f"오늘의 스피킹 세션 시작 [{topic.track.upper()}]{srs_tag}\n"
            f"(완료 시 Anki Speaking 1 -> 0 자동 반영)\n\n"
            f"[Step 1/3 — 워밍업 1/2]\n"
            f"준비 없이 바로 30~45초 음성으로 답하세요:\n"
            f"Q: {warmups[0]}"
        )
        return {
            "mode": "session",
            "session_id": session.id,
            "step": session.step,
            "message": msg,
            "audio_bytes": None,
            "candidates": [],
        }

    def cancel_session(self) -> Dict[str, Any]:
        cancelled = self.store.cancel_active_session()
        msg = "진행 중인 스피킹 세션을 취소했습니다." if cancelled else "진행 중인 스피킹 세션이 없습니다."
        return {"cancelled": cancelled, "message": msg}

    def handle_voice(
        self,
        audio_bytes: bytes,
        filename: str = "voice.ogg",
        force_debrief: bool = False,
    ) -> Dict[str, Any]:
        session = None if force_debrief else self.store.get_active_session()
        if session is None:
            return self._handle_debrief(audio_bytes, filename)

        if session.step == "warmup_1":
            return self._handle_warmup_1(session, audio_bytes, filename)
        if session.step == "warmup_2":
            return self._handle_warmup_2(session, audio_bytes, filename)
        if session.step == "main_pass1":
            return self._handle_main_pass1(session, audio_bytes, filename)
        if session.step == "main_pass2":
            return self._handle_main_pass2(session, audio_bytes, filename)
        if session.step == "followup":
            return self._handle_followup(session, audio_bytes, filename)
        return self._handle_debrief(audio_bytes, filename)

    def _handle_warmup_1(
        self, session: SessionState, audio_bytes: bytes, filename: str
    ) -> Dict[str, Any]:
        tr = self.stt.transcribe(audio_bytes, filename=filename)
        prompt = session.warmup_prompts[0] if session.warmup_prompts else ""
        fb: CoachFeedback = self.coach.evaluate_warmup(prompt, tr.transcript, tr.metrics)
        self.store.save_attempt(session.id, "warmup_1", tr.transcript, tr.metrics, fb.model_dump())
        self.store.advance_step(session.id, "warmup_2")

        next_q = session.warmup_prompts[1] if len(session.warmup_prompts) > 1 else "What is your plan for today?"
        lines = [
            f"[워밍업 1 완료] {_format_metrics(tr.metrics)}",
            f"피드백: {fb.summary}",
        ]
        if fb.native_model:
            lines.append(f"자연스러운 표현: {fb.native_model}")
        lines.append(f"\n[Step 1/3 — 워밍업 2/2]\n바로 이어서 30~45초 답하세요:\nQ: {next_q}")
        return {
            "mode": "session",
            "session_id": session.id,
            "step": "warmup_2",
            "message": "\n".join(lines),
            "audio_bytes": None,
            "candidates": [],
        }

    def _handle_warmup_2(
        self, session: SessionState, audio_bytes: bytes, filename: str
    ) -> Dict[str, Any]:
        tr = self.stt.transcribe(audio_bytes, filename=filename)
        prompt = session.warmup_prompts[1] if len(session.warmup_prompts) > 1 else ""
        fb: CoachFeedback = self.coach.evaluate_warmup(prompt, tr.transcript, tr.metrics)
        self.store.save_attempt(session.id, "warmup_2", tr.transcript, tr.metrics, fb.model_dump())
        self.store.advance_step(session.id, "main_pass1")

        topic = get_topic_by_id(session.topic_id)
        bullets = ""
        if topic and topic.bullets:
            bullets = "\n포인트:\n" + "\n".join(f"- {b}" for b in topic.bullets)
        vocab_block = ""
        if session.mission_vocab:
            vocab_block = "\n\nAnki 보너스 표현 (자연스러울 때만 1~2개 활용):\n" + "\n".join(
                f"- {v}" for v in session.mission_vocab
            )

        msg = (
            f"[워밍업 2 완료] {_format_metrics(tr.metrics)}\n"
            f"피드백: {fb.summary}\n\n"
            f"[Step 2/3 — 메인 1차 발화 (목표 90초)]\n"
            f"주제 [{session.track.upper()}]: {session.topic_prompt}"
            f"{bullets}{vocab_block}\n\n"
            f"30초 정리 후 90초 내외로 음성 메시지를 보내세요."
        )
        return {
            "mode": "session",
            "session_id": session.id,
            "step": "main_pass1",
            "message": msg,
            "audio_bytes": None,
            "candidates": [],
        }

    def _handle_main_pass1(
        self, session: SessionState, audio_bytes: bytes, filename: str
    ) -> Dict[str, Any]:
        tr = self.stt.transcribe(audio_bytes, filename=filename)
        fb: CoachFeedback = self.coach.evaluate_main_pass1(
            session.topic_prompt,
            session.track,
            session.mission_vocab,
            tr.transcript,
            tr.metrics,
        )
        self.store.save_attempt(session.id, "main_pass1", tr.transcript, tr.metrics, fb.model_dump())
        self._persist_candidates(session.id, fb.card_candidates)
        self.store.advance_step(session.id, "main_pass2")

        audio = self.tts_fn(fb.native_model) if fb.native_model else None
        lines = [
            f"[메인 1차 분석] {_format_metrics(tr.metrics)}",
            f"점수: {fb.score}/10" if fb.score is not None else "",
            f"진단: {fb.summary}",
        ]
        corr = _format_corrections(fb.corrections)
        if corr:
            lines.append(f"\n주요 교정:\n{corr}")
        if fb.native_model:
            lines.append(f"\n원어민 대안 (음성 확인 후 따라 말하기):\n{fb.native_model}")
        lines.append(
            "\n[Step 2/3 — 메인 2차 압축 재발화 (목표 60초)]\n"
            "위 교정 1~2가지만 챙겨서 같은 주제를 60초로 더 빠르고 매끄럽게 다시 말해 보내세요."
        )
        return {
            "mode": "session",
            "session_id": session.id,
            "step": "main_pass2",
            "message": "\n".join(line for line in lines if line),
            "audio_bytes": audio,
            "candidates": [],
        }

    def _handle_main_pass2(
        self, session: SessionState, audio_bytes: bytes, filename: str
    ) -> Dict[str, Any]:
        tr = self.stt.transcribe(audio_bytes, filename=filename)
        p1_row = self.store.get_attempt(session.id, "main_pass1")
        p1_transcript = p1_row["transcript"] if p1_row else ""
        p1_metrics = SpeakingMetrics(**p1_row["metrics"]) if p1_row else SpeakingMetrics()

        fb: CoachFeedback = self.coach.evaluate_main_pass2(
            session.topic_prompt,
            session.track,
            p1_transcript,
            p1_metrics,
            tr.transcript,
            tr.metrics,
        )
        self.store.save_attempt(session.id, "main_pass2", tr.transcript, tr.metrics, fb.model_dump())
        self._persist_candidates(session.id, fb.card_candidates)

        followup_q = fb.followup_question or "What would you do differently if you faced that situation again?"
        self.store.advance_step(session.id, "followup", followup_question=followup_q)

        # 메인 2차 점수 기준으로 토픽 SRS 예약
        if fb.score is not None:
            self.store.record_topic_outcome(session.topic_id, score=fb.score, today=self.today_fn())

        lines = [
            f"[메인 2차 압축 완료] {_format_metrics(tr.metrics)}",
            _format_delta(p1_metrics, tr.metrics),
            f"평가: {fb.summary}",
        ]
        corr = _format_corrections(fb.corrections)
        if corr:
            lines.append(f"\n남은 보완점:\n{corr}")
        lines.append(
            f"\n[Step 3/3 — 즉흥 꼬리질문 (30~60초)]\n"
            f"준비 없이 바로 답하세요:\nQ: {followup_q}"
        )
        return {
            "mode": "session",
            "session_id": session.id,
            "step": "followup",
            "message": "\n".join(lines),
            "audio_bytes": None,
            "candidates": [],
        }

    def _handle_followup(
        self, session: SessionState, audio_bytes: bytes, filename: str
    ) -> Dict[str, Any]:
        tr = self.stt.transcribe(audio_bytes, filename=filename)
        fq = session.followup_question or ""
        fb: CoachFeedback = self.coach.evaluate_followup(fq, tr.transcript, tr.metrics)
        self.store.save_attempt(session.id, "followup", tr.transcript, tr.metrics, fb.model_dump())
        self._persist_candidates(session.id, fb.card_candidates)
        self.store.complete_session(session.id)

        today = self.today_fn()
        streaks = self.store.compute_streaks(today=today)
        recent_14d = self.store.recent_metrics_summary(days=14, today=today)
        recent_sessions = self.store.list_recent_sessions(limit=14)

        try:
            self.tracker.update_log(streaks, recent_14d, recent_sessions)
        except Exception as e:
            logger.warning("Failed to update Anki speaking tracker log: %s", e)

        tracker_status = "Anki Speaking 1 -> 0 반영 완료"
        try:
            self.tracker.mark_done()
            self._notify_anki_changed()
        except Exception as e:
            logger.warning("Failed to mark Anki speaking tracker done: %s", e)
            tracker_status = f"Anki 트래커 갱신 실패 ({type(e).__name__})"

        all_candidates = self.store.list_session_candidates(session.id)
        audio = self.tts_fn(fb.native_model) if fb.native_model else None

        lines = [
            f"[Step 3/3 꼬리질문 완료] {_format_metrics(tr.metrics)}",
            f"평가: {fb.summary}",
        ]
        corr = _format_corrections(fb.corrections)
        if corr:
            lines.append(f"\n교정:\n{corr}")
        if fb.native_model:
            lines.append(f"\n원어민 대안:\n{fb.native_model}")
        lines.append(
            f"\n오늘 스피킹 완료 (연속 {streaks['current']}일 · 누적 {streaks['total_completed']}회)\n"
            f"{tracker_status}"
        )
        if all_candidates:
            lines.append("\n아래 버튼에서 Anki에 넣을 표현만 골라 추가하세요:")
        return {
            "mode": "session",
            "session_id": session.id,
            "step": "completed",
            "message": "\n".join(lines),
            "audio_bytes": audio,
            "candidates": all_candidates,
        }

    def _handle_debrief(self, audio_bytes: bytes, filename: str) -> Dict[str, Any]:
        # 외부 대화 회수는 한국어/영어 혼용이 가능하므로 language=None 자동 감지
        try:
            tr = self.stt.transcribe(audio_bytes, filename=filename, language=None)
        except TypeError:
            tr = self.stt.transcribe(audio_bytes, filename=filename)
        fb: CoachFeedback = self.coach.analyze_debrief(tr.transcript)
        self.store.save_attempt(None, "debrief", tr.transcript, tr.metrics, fb.model_dump())
        saved = self._persist_candidates(None, fb.card_candidates)
        audio = self.tts_fn(fb.native_model) if fb.native_model else None

        lines = [
            "[외부 대화 표현 회수]",
            f"요약: {fb.summary}",
        ]
        corr = _format_corrections(fb.corrections)
        if corr:
            lines.append(f"\n표현 포인트:\n{corr}")
        if fb.native_model:
            lines.append(f"\n대표 표현:\n{fb.native_model}")
        if saved:
            lines.append("\nAnki에 추가할 표현을 버튼으로 선택하세요:")
        return {
            "mode": "debrief",
            "session_id": None,
            "step": "completed",
            "message": "\n".join(lines),
            "audio_bytes": audio,
            "candidates": saved,
        }

    def register_candidate(self, candidate_id: int) -> Dict[str, Any]:
        row = self.store.get_candidate(candidate_id)
        if not row:
            return {"success": False, "error": "후보를 찾을 수 없습니다.", "message": "후보를 찾을 수 없습니다."}
        if row["added_note_id"] is not None:
            return {
                "success": True,
                "already_added": True,
                "note_id": row["added_note_id"],
                "message": "이미 Anki에 등록된 표현입니다.",
            }

        cand = CardCandidate(**row["candidate"])
        if cand.kind == "vocab":
            payload: Dict[str, Any] = {
                "word": cand.text,
                "meaning": cand.translation,
                "use_free_router": True,
                "tags": [SPEAKING_CARD_TAG],
            }
            label = "단어"
        elif cand.kind == "grammar" and cand.answer:
            payload = {
                "sentence": cand.text,
                "answer": cand.answer,
                "distractors": cand.distractors,
                "translation": cand.translation,
                "tags": [SPEAKING_CARD_TAG],
            }
            label = "문법"
        else:
            payload = {
                "sentence": cand.text,
                "translation": cand.translation,
                "use_free_router": True,
                "tags": [SPEAKING_CARD_TAG],
            }
            cand_kind = "sentence"
            label = "문장"
            res = self.card_creator(cand_kind, payload)
            return self._finalize_registration(candidate_id, label, cand.text, res)

        res = self.card_creator(cand.kind, payload)
        return self._finalize_registration(candidate_id, label, cand.text, res)

    def _finalize_registration(
        self, candidate_id: int, label: str, text: str, res: Dict[str, Any]
    ) -> Dict[str, Any]:
        if res.get("duplicate"):
            return {"success": True, "duplicate": True, "message": f"이미 있는 {label} 카드입니다: {text}"}
        if not res.get("success"):
            err = res.get("error") or "알 수 없는 오류"
            return {"success": False, "error": err, "message": f"등록 실패: {err}"}
        note_id = res.get("note_id")
        if note_id:
            self.store.mark_candidate_added(candidate_id, int(note_id))
        self._notify_anki_changed()
        return {
            "success": True,
            "note_id": note_id,
            "message": f"{label} 카드 등록 완료 ({SPEAKING_CARD_TAG}): {text}",
        }

    def sync_tracker_log(self) -> Dict[str, Any]:
        today = self.today_fn()
        streaks = self.store.compute_streaks(today=today)
        recent_14d = self.store.recent_metrics_summary(days=14, today=today)
        recent_sessions = self.store.list_recent_sessions(limit=14)
        return self.tracker.update_log(streaks, recent_14d, recent_sessions)

    def get_stats(self) -> Dict[str, Any]:
        today = self.today_fn()
        streaks = self.store.compute_streaks(today=today)
        recent = self.store.recent_metrics_summary(days=14, today=today)
        done_today = self.store.has_completed_on(today.isoformat())
        due_topics = self.store.get_due_topic_ids(today=today)
        msg = (
            f"스피킹 통계 ({today.isoformat()})\n"
            f"- 오늘 완료: {'완료 (0 남음)' if done_today else '미완료 (1 남음)'}\n"
            f"- 연속 스트릭: {streaks['current']}일 (최장 {streaks['longest']}일, 누적 {streaks['total_completed']}회)\n"
            f"- 최근 14일 ({recent['attempts_count']}회 발화): "
            f"평균 {recent['avg_wpm']} WPM · 필러 {recent['avg_fillers']}회 · 긴 침묵 {recent['avg_long_pauses']}회\n"
            f"- SRS 복습 대기 주제: {len(due_topics)}개"
        )
        return {
            "today": today.isoformat(),
            "done_today": done_today,
            "streaks": streaks,
            "recent_14d": recent,
            "due_topics_count": len(due_topics),
            "message": msg,
        }
