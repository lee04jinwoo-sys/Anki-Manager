"""Channel-agnostic v2 Anki-native speaking queue orchestrator."""
from __future__ import annotations

import datetime as dt
import logging
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from zoneinfo import ZoneInfo

from speaking.anki_deck import AnkiSpeakingDeck
from speaking.coach import SpeakingCoach
from speaking.models import (
    CardCandidate,
    CardEvaluation,
    QueueCounts,
    SpeakingCard,
    SpeakingMetrics,
)
from speaking.speech import (
    GroqWhisperClient,
    save_audio_file,
    synthesize_coaching_audio,
)
from speaking.store import SpeakingStore

logger = logging.getLogger("speaking.service")

TORONTO_TZ = ZoneInfo("America/Toronto")
SPEAKING_CARD_TAG = "speaking"
_EASE_NAMES = {1: "Again", 2: "Hard", 3: "Good", 4: "Easy"}


def _toronto_today() -> dt.date:
    now = dt.datetime.now(TORONTO_TZ)
    # Anki 일자 경계(새벽 4시)와 동일
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
        f"재녹음 변화: WPM {p1.wpm:.0f} -> {p2.wpm:.0f} ({dwpm:+.0f}), "
        f"필러 {p1.filler_count} -> {p2.filler_count} ({dfill:+d}), "
        f"긴 침묵 {p1.long_pause_count} -> {p2.long_pause_count} ({dpause:+d})"
    )


def _default_card_creator(kind: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    from backend.schemas.cards import (
        GrammarCreateRequest,
        SentenceCreateRequest,
        VocabCreateRequest,
    )
    from backend.services import card_service

    if kind == "vocab":
        res = card_service.create_vocab_card(VocabCreateRequest(**payload))
    elif kind == "grammar":
        res = card_service.create_grammar_card(GrammarCreateRequest(**payload))
    else:
        res = card_service.create_sentence_card(SentenceCreateRequest(**payload))
    return res.model_dump()


class SpeakingService:
    def __init__(
        self,
        store: Optional[SpeakingStore] = None,
        anki_deck: Optional[Any] = None,
        stt: Optional[Any] = None,
        coach: Optional[Any] = None,
        tts_fn: Optional[Callable[[str], Optional[bytes]]] = None,
        audio_dir: Optional[Path] = None,
        card_creator: Optional[Callable[[str, Dict[str, Any]], Dict[str, Any]]] = None,
        on_anki_changed: Optional[Callable[[], None]] = None,
        today_fn: Optional[Callable[[], dt.date]] = None,
    ) -> None:
        self.store = store or SpeakingStore()
        self.anki_deck = anki_deck or AnkiSpeakingDeck()
        self.stt = stt or GroqWhisperClient()
        self.coach = coach or SpeakingCoach()
        self.tts_fn = tts_fn or synthesize_coaching_audio
        self.audio_dir = audio_dir
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

    def _save_audio_safe(
        self, audio_bytes: bytes, session_date: str, label: str, filename: str
    ) -> Optional[str]:
        try:
            path = save_audio_file(
                audio_bytes=audio_bytes,
                session_date=session_date,
                label=label,
                filename=filename,
                base_dir=self.audio_dir,
            )
            return str(path)
        except Exception as e:
            logger.warning("Audio archive write failed (%s): %s", label, e)
            return None

    def _persist_candidates(
        self, session_date: str, attempt_id: Optional[int], candidates: List[CardCandidate]
    ) -> List[Dict[str, Any]]:
        saved = []
        for cand in candidates:
            cid = self.store.save_candidate(session_date, attempt_id, cand)
            saved.append({"id": cid, "attempt_id": attempt_id, **cand.model_dump()})
        return saved

    def _format_card_prompt(
        self,
        card: SpeakingCard,
        index: int,
        total: int,
        header: Optional[str] = None,
    ) -> str:
        lines: List[str] = []
        if header:
            lines.extend([header, ""])

        if not card.is_new:
            history = self.store.list_card_history(card.card_id, limit=1, rated_only=True)
            if history:
                prev = history[0]
                model_hint = f" · 참고: {prev['native_model']}" if prev.get("native_model") else ""
                lines.append(
                    f"(직전 {prev['session_date']}: 점수 {prev.get('score') or '-'} · {prev.get('wpm', 0):.0f} WPM{model_hint})"
                )
                lines.append("")

        lines.append(card.prompt_text)
        return "\n".join(lines).strip()

    @staticmethod
    def _pick_card_from_queue(
        cards: List[SpeakingCard], active_card_id: Optional[int]
    ) -> tuple[SpeakingCard, int]:
        if active_card_id is not None:
            for idx, c in enumerate(cards):
                if c.card_id == active_card_id:
                    return c, idx
        return cards[0], 0

    def start_or_resume_today(self) -> Dict[str, Any]:
        today_str = self.today_fn().isoformat()
        counts, cards = self.anki_deck.fetch_today_queue()
        existing = self.store.get_daily_queue(today_str)

        if not cards:
            if existing and existing["completed_count"] > 0:
                if existing["status"] != "completed":
                    self.store.set_queue_state(today_str, active_card_id=None, status="completed")
                return self.get_daily_summary(completed_just_now=False)
            return {
                "mode": "queue",
                "status": "empty",
                "date": today_str,
                "card_id": None,
                "recommended_ease": None,
                "show_rating_buttons": False,
                "counts": counts.model_dump(),
                "message": "오늘 남은 Speaking 카드가 없습니다 (0장).\n외부 대화에서 막힌 표현을 정리하려면 음성 메시지를 바로 보내세요.",
                "audio_bytes": None,
                "candidates": [],
            }

        completed_so_far = existing["completed_count"] if existing else 0
        total_assigned = max(
            existing["total_assigned"] if existing else 0,
            completed_so_far + len(cards),
        )
        preferred_id = existing["active_card_id"] if existing else None
        card, _ = self._pick_card_from_queue(cards, preferred_id)
        self.store.upsert_daily_queue(
            session_date=today_str,
            total_assigned=total_assigned,
            active_card_id=card.card_id,
            status="active",
            retry_mode=False,
        )

        index = min(completed_so_far + 1, total_assigned)
        return {
            "mode": "queue",
            "status": "question",
            "date": today_str,
            "card_id": card.card_id,
            "recommended_ease": None,
            "show_rating_buttons": False,
            "counts": counts.model_dump(),
            "message": self._format_card_prompt(card, index, total_assigned),
            "audio_bytes": None,
            "candidates": [],
        }

    def submit_voice(
        self,
        audio_bytes: bytes,
        filename: str = "voice.ogg",
        force_debrief: bool = False,
    ) -> Dict[str, Any]:
        today_str = self.today_fn().isoformat()
        q = None if force_debrief else self.store.get_daily_queue(today_str)
        if not q or q["status"] != "active" or not q.get("active_card_id"):
            return self._handle_debrief(today_str, audio_bytes, filename)

        counts, cards = self.anki_deck.fetch_today_queue()
        if not cards:
            return self._handle_debrief(today_str, audio_bytes, filename)

        card, _ = self._pick_card_from_queue(cards, q["active_card_id"])
        is_retry = bool(q["retry_mode"])
        prev_attempt = self.store.get_latest_attempt_for_card_today(today_str, card.card_id)

        label = f"card_{card.card_id}_r2" if is_retry and prev_attempt else f"card_{card.card_id}"
        audio_path = self._save_audio_safe(audio_bytes, today_str, label, filename)
        tr = self.stt.transcribe(audio_bytes, filename=filename, language="en")

        delta_line = ""
        if is_retry and prev_attempt:
            p1_metrics = SpeakingMetrics(**prev_attempt["metrics"])
            ev: CardEvaluation = self.coach.evaluate_retry(
                card,
                prev_attempt["transcript"],
                p1_metrics,
                tr.transcript,
                tr.metrics,
            )
            attempt_num = int(prev_attempt["attempt_num"]) + 1
            delta_line = _format_delta(p1_metrics, tr.metrics)
        else:
            prior_history = self.store.list_card_history(card.card_id, limit=3, rated_only=True)
            ev = self.coach.evaluate_card(card, tr.transcript, tr.metrics, prior_history=prior_history)
            attempt_num = 1

        attempt_id = self.store.save_card_attempt(
            session_date=today_str,
            card_id=card.card_id,
            note_id=card.note_id,
            topic_id=card.topic_id,
            prompt_text=card.prompt_text,
            attempt_num=attempt_num,
            mode="card",
            transcript=tr.transcript,
            audio_path=audio_path,
            metrics=tr.metrics,
            feedback=ev.model_dump(),
            score=ev.score,
        )
        saved_candidates = self._persist_candidates(today_str, attempt_id, ev.card_candidates)
        self.store.set_queue_state(today_str, active_card_id=card.card_id, retry_mode=False)

        audio = self.tts_fn(ev.native_model) if ev.native_model else None
        ease_name = _EASE_NAMES.get(ev.recommended_ease, "Good")
        lines = [
            f"[채점 · {card.category}] {_format_metrics(tr.metrics)}",
            delta_line,
            f"점수: {ev.score}/10 (추천: {ease_name})",
            f"피드백: {ev.summary}",
        ]
        if ev.corrections:
            lines.append("\n교정:\n" + "\n".join(f"- {c}" for c in ev.corrections))
        if ev.native_model:
            lines.append(f"\n원어민 대안:\n{ev.native_model}")
        lines.append("\n아래 버튼으로 [재녹음]하거나 Anki 평가(Again/Hard/Good/Easy)를 선택하세요.")

        return {
            "mode": "card",
            "status": "evaluated",
            "date": today_str,
            "card_id": card.card_id,
            "recommended_ease": ev.recommended_ease,
            "show_rating_buttons": True,
            "counts": counts.model_dump(),
            "message": "\n".join(line for line in lines if line),
            "audio_bytes": audio,
            "candidates": saved_candidates,
        }

    def request_retry(self) -> Dict[str, Any]:
        today_str = self.today_fn().isoformat()
        q = self.store.get_daily_queue(today_str)
        if not q or q["status"] != "active" or not q.get("active_card_id"):
            return {
                "mode": "queue",
                "status": "empty",
                "date": today_str,
                "card_id": None,
                "recommended_ease": None,
                "show_rating_buttons": False,
                "message": "재녹음할 활성 카드가 없습니다. /today로 오늘 카드를 먼저 시작하세요.",
                "audio_bytes": None,
                "candidates": [],
            }
        self.store.set_queue_state(today_str, active_card_id=q["active_card_id"], retry_mode=True)
        return {
            "mode": "queue",
            "status": "retry_ready",
            "date": today_str,
            "card_id": q["active_card_id"],
            "recommended_ease": None,
            "show_rating_buttons": False,
            "message": "같은 질문 재녹음 준비 완료. 방금 교정을 챙겨 45~60초로 다시 녹음해 보내세요.",
            "audio_bytes": None,
            "candidates": [],
        }

    def rate_current_card(self, card_id: int, ease: int) -> Dict[str, Any]:
        today_str = self.today_fn().isoformat()
        attempt = self.store.get_latest_attempt_for_card_today(today_str, card_id)
        if attempt and attempt.get("ease") is not None:
            # 더블 탭이나 지난 메시지의 버튼: 같은 답변을 Anki에 두 번 기록하지 않는다.
            return {
                "mode": "queue",
                "status": "already_rated",
                "date": today_str,
                "card_id": card_id,
                "recommended_ease": None,
                "show_rating_buttons": False,
                "message": "이미 평가한 카드입니다. /today로 다음 카드를 이어가세요.",
                "audio_bytes": None,
                "candidates": [],
            }

        self.anki_deck.answer_speaking_card(card_id, ease)

        if attempt:
            self.store.mark_attempt_rated(attempt["id"], ease)
            note_id = attempt.get("note_id")
            if note_id:
                try:
                    history = self.store.list_card_history(card_id, limit=5, rated_only=True)
                    self.anki_deck.update_card_back_log(int(note_id), history)
                except Exception as e:
                    logger.warning("Failed to update card back log (note %s): %s", note_id, e)

        self._notify_anki_changed()

        counts, remaining = self.anki_deck.fetch_today_queue()
        q = self.store.get_daily_queue(today_str)
        if not remaining or counts.remaining == 0:
            if q:
                self.store.set_queue_state(
                    today_str,
                    active_card_id=None,
                    retry_mode=False,
                    increment_completed=True,
                    status="completed",
                )
            else:
                self.store.upsert_daily_queue(
                    today_str, total_assigned=1, active_card_id=None, status="completed"
                )
            return self.get_daily_summary(completed_just_now=True)

        # 방금 평가한 카드가 learning 등으로 남더라도 다른 카드가 있으면 우선 다음 카드로 넘김
        next_card = remaining[0]
        if next_card.card_id == card_id and len(remaining) > 1:
            next_card = remaining[1]

        total_assigned = max(q["total_assigned"] if q else 1, (q["completed_count"] if q else 0) + 1 + len(remaining))
        if q:
            updated_q = self.store.set_queue_state(
                today_str,
                active_card_id=next_card.card_id,
                retry_mode=False,
                increment_completed=True,
                status="active",
            )
            index = min(updated_q["completed_count"] + 1, total_assigned)
        else:
            self.store.upsert_daily_queue(
                today_str, total_assigned=total_assigned, active_card_id=next_card.card_id, status="active"
            )
            index = 1

        ease_name = _EASE_NAMES.get(ease, str(ease))
        header = f"Anki 기록 완료 ({ease_name}) · 남은 카드 {len(remaining)}장"
        return {
            "mode": "queue",
            "status": "next_card",
            "date": today_str,
            "card_id": next_card.card_id,
            "recommended_ease": None,
            "show_rating_buttons": False,
            "counts": counts.model_dump(),
            "message": self._format_card_prompt(next_card, index, total_assigned, header=header),
            "audio_bytes": None,
            "candidates": [],
        }

    def skip_current_card(self) -> Dict[str, Any]:
        today_str = self.today_fn().isoformat()
        counts, cards = self.anki_deck.fetch_today_queue()
        if not cards:
            return {
                "mode": "queue",
                "status": "empty",
                "date": today_str,
                "card_id": None,
                "recommended_ease": None,
                "show_rating_buttons": False,
                "counts": counts.model_dump(),
                "message": "건너뛸 카드가 없습니다 (오늘 남은 카드 0장).",
                "audio_bytes": None,
                "candidates": [],
            }
        if len(cards) == 1:
            return {
                "mode": "queue",
                "status": "question",
                "date": today_str,
                "card_id": cards[0].card_id,
                "recommended_ease": None,
                "show_rating_buttons": False,
                "counts": counts.model_dump(),
                "message": "오늘 남은 카드가 1장뿐입니다. 답변하거나 내일 이어서 진행하세요.",
                "audio_bytes": None,
                "candidates": [],
            }

        q = self.store.get_daily_queue(today_str)
        active_id = q["active_card_id"] if q else cards[0].card_id
        _, idx = self._pick_card_from_queue(cards, active_id)
        next_card = cards[(idx + 1) % len(cards)]
        total_assigned = q["total_assigned"] if q else len(cards)
        completed = q["completed_count"] if q else 0
        self.store.upsert_daily_queue(
            today_str, total_assigned=total_assigned, active_card_id=next_card.card_id, status="active"
        )
        index = min(completed + 1, total_assigned)
        return {
            "mode": "queue",
            "status": "question",
            "date": today_str,
            "card_id": next_card.card_id,
            "recommended_ease": None,
            "show_rating_buttons": False,
            "counts": counts.model_dump(),
            "message": self._format_card_prompt(
                next_card, index, total_assigned, header="다른 카드로 순서를 바꿨습니다."
            ),
            "audio_bytes": None,
            "candidates": [],
        }

    def get_daily_summary(self, completed_just_now: bool = False) -> Dict[str, Any]:
        today = self.today_fn()
        today_str = today.isoformat()
        attempts = self.store.list_today_attempts(today_str, mode="card")
        rated_attempts = [a for a in attempts if a.get("ease") is not None]
        sample = rated_attempts or attempts
        streaks = self.store.compute_streaks(today=today)
        candidates = self.store.list_today_candidates(today_str)

        if sample:
            avg_wpm = round(sum(a["wpm"] for a in sample) / len(sample), 1)
            avg_fill = round(sum(a["filler_count"] for a in sample) / len(sample), 1)
            total_sec = sum(a["duration_sec"] for a in sample)
            best_models = [a["native_model"] for a in sample if a.get("native_model")][:3]
        else:
            avg_wpm = 0.0
            avg_fill = 0.0
            total_sec = 0.0
            best_models = []

        unique_cards = len({a["card_id"] for a in sample if a.get("card_id")})
        title = (
            f"오늘 스피킹 세트 완료! (연속 {streaks['current']}일 · 누적 {streaks['total_completed']}일)"
            if completed_just_now
            else f"오늘 스피킹 요약 ({today_str})"
        )
        lines = [
            title,
            f"- 완료 카드: {unique_cards}장 (총 녹음 {len(sample)}회 · {total_sec:.0f}초)",
            f"- 오늘 평균: {avg_wpm} WPM · 필러 {avg_fill}회",
        ]
        if best_models:
            lines.append("\n오늘 핵심 원어민 표현:")
            lines.extend(f"- {m}" for m in best_models)
        if candidates:
            lines.append("\n아래 버튼에서 Anki Sentence/Vocab/Grammar 덱에 넣을 표현만 골라 추가하세요:")

        return {
            "mode": "queue",
            "status": "day_completed" if completed_just_now else "summary",
            "date": today_str,
            "card_id": None,
            "recommended_ease": None,
            "show_rating_buttons": False,
            "message": "\n".join(lines),
            "audio_bytes": None,
            "candidates": candidates,
        }

    def _handle_debrief(
        self, today_str: str, audio_bytes: bytes, filename: str
    ) -> Dict[str, Any]:
        audio_path = self._save_audio_safe(audio_bytes, today_str, "debrief", filename)
        try:
            tr = self.stt.transcribe(audio_bytes, filename=filename, language=None)
        except TypeError:
            tr = self.stt.transcribe(audio_bytes, filename=filename)

        ev: CardEvaluation = self.coach.analyze_debrief(tr.transcript)
        attempt_id = self.store.save_card_attempt(
            session_date=today_str,
            card_id=None,
            note_id=None,
            topic_id="debrief",
            prompt_text="external conversation debrief",
            attempt_num=1,
            mode="debrief",
            transcript=tr.transcript,
            audio_path=audio_path,
            metrics=tr.metrics,
            feedback=ev.model_dump(),
            score=None,
        )
        saved = self._persist_candidates(today_str, attempt_id, ev.card_candidates)
        audio = self.tts_fn(ev.native_model) if ev.native_model else None

        lines = ["[외부 대화 표현 회수]", f"요약: {ev.summary}"]
        if ev.corrections:
            lines.append("\n표현 포인트:\n" + "\n".join(f"- {c}" for c in ev.corrections))
        if ev.native_model:
            lines.append(f"\n대표 표현:\n{ev.native_model}")
        if saved:
            lines.append("\nAnki에 추가할 표현을 버튼으로 선택하세요:")

        return {
            "mode": "debrief",
            "status": "debrief_done",
            "date": today_str,
            "card_id": None,
            "recommended_ease": None,
            "show_rating_buttons": False,
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
            target_kind = "vocab"
            label = "단어"
        elif cand.kind == "grammar" and cand.answer:
            payload = {
                "sentence": cand.text,
                "answer": cand.answer,
                "distractors": cand.distractors,
                "translation": cand.translation,
                "tags": [SPEAKING_CARD_TAG],
            }
            target_kind = "grammar"
            label = "문법"
        else:
            payload = {
                "sentence": cand.text,
                "translation": cand.translation,
                "use_free_router": True,
                "tags": [SPEAKING_CARD_TAG],
            }
            target_kind = "sentence"
            label = "문장"

        res = self.card_creator(target_kind, payload)
        if res.get("duplicate"):
            return {"success": True, "duplicate": True, "message": f"이미 있는 {label} 카드입니다: {cand.text}"}
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
            "message": f"{label} 카드 등록 완료 ({SPEAKING_CARD_TAG}): {cand.text}",
        }

    def register_attempt_candidates(self, attempt_id: int) -> Dict[str, Any]:
        """한 번의 답변에서 나온 후보를 전부 Anki에 등록한다(이미 등록된 것은 건너뜀)."""
        rows = self.store.list_candidates_for_attempt(attempt_id)
        added = skipped = failed = 0
        for row in rows:
            if row.get("added_note_id") is not None:
                skipped += 1
                continue
            res = self.register_candidate(int(row["id"]))
            if not res.get("success"):
                failed += 1
            elif res.get("duplicate") or res.get("already_added"):
                skipped += 1
            else:
                added += 1
        parts = [f"{added}장 등록"]
        if skipped:
            parts.append(f"{skipped}장은 이미 있음")
        if failed:
            parts.append(f"{failed}장 실패")
        return {
            "success": failed == 0,
            "added": added,
            "skipped": skipped,
            "failed": failed,
            "message": "전부 추가: " + " · ".join(parts),
        }

    def get_stats(self) -> Dict[str, Any]:
        today = self.today_fn()
        streaks = self.store.compute_streaks(today=today)
        recent = self.store.recent_metrics_summary(days=14, today=today)
        try:
            counts = self.anki_deck.get_deck_counts()
        except Exception:
            counts = QueueCounts()

        msg = (
            f"스피킹 통계 ({today.isoformat()})\n"
            f"- 오늘 Anki 남은 카드: {counts.remaining}장 (새 {counts.new_count} · 복습 {counts.review_count + counts.learn_count} / 전체 {counts.total_in_deck}장)\n"
            f"- 연속 스트릭: {streaks['current']}일 (최장 {streaks['longest']}일, 완료일 {streaks['total_completed']}일)\n"
            f"- 최근 14일 ({recent['attempts_count']}회 녹음): "
            f"평균 {recent['avg_wpm']} WPM · 필러 {recent['avg_fillers']}회 · 긴 침묵 {recent['avg_long_pauses']}회"
        )
        return {
            "today": today.isoformat(),
            "counts": counts.model_dump(),
            "streaks": streaks,
            "recent_14d": recent,
            "message": msg,
        }
