"""Anki Speaking 1-card tracker bridge (1 -> 0) and Anki mission-vocab fetcher."""
from __future__ import annotations

import html
import logging
import random
import re
from typing import Any, Callable, Dict, List, Optional

from integrations.anki_connect import AnkiConnector

logger = logging.getLogger("speaking.tracker")

SPEAKING_DECK = "1. Language::1.1. English::Speaking"
TRACKER_MODEL = "Basic"
TRACKER_TAG = "speaking::tracker"
TRACKER_FRONT = (
    "오늘의 영어 스피킹 15분 (3단계)<br><br>"
    "직접 누르지 말고 텔레그램 <b>@ankimanager_bot</b> 에서 <code>/speak</code> 완료 시 자동으로 0이 됩니다."
)
TRACKER_BACK = "Step 1 워밍업 → Step 2 메인 90초/60초 압축 → Step 3 꼬리질문 완료"

_HTML_TAG_RE = re.compile(r"<.*?>")


def _clean_field(value: str) -> str:
    return _HTML_TAG_RE.sub("", html.unescape(value or "")).strip()


def _short(text: str, max_len: int = 44) -> str:
    clean = " ".join((text or "").split()).replace("|", "/")
    return clean if len(clean) <= max_len else clean[: max_len - 3] + "..."


def format_tracker_fields(
    streaks: Dict[str, Any],
    recent_14d: Dict[str, Any],
    recent_sessions: List[Dict[str, Any]],
) -> Dict[str, str]:
    """Anki Basic 카드(Markdown 지원)의 앞면·뒷면에 표시할 스피킹 누적 로그를 생성한다."""
    cur = streaks.get("current", 0)
    longest = streaks.get("longest", 0)
    total = streaks.get("total_completed", 0)
    avg_wpm = recent_14d.get("avg_wpm", 0.0)
    avg_fillers = recent_14d.get("avg_fillers", 0.0)
    avg_pauses = recent_14d.get("avg_long_pauses", 0.0)

    front_lines = [
        "### 오늘의 영어 스피킹 (15분 · 3단계)",
        "직접 누르지 말고 텔레그램 `@ankimanager_bot`에서 `/speak` 완료 시 자동으로 `0`이 됩니다.",
        "",
        f"- **스트릭**: 연속 {cur}일 (최장 {longest}일 · 누적 {total}회)",
        f"- **최근 14일 평균**: {avg_wpm} WPM · 필러 {avg_fillers}회 · 긴 침묵 {avg_pauses}회",
    ]

    if recent_sessions:
        latest = recent_sessions[0]
        p1_wpm = latest.get("pass1_wpm")
        p2_wpm = latest.get("pass2_wpm")
        wpm_str = (
            f"{p1_wpm:.0f} -> {p2_wpm:.0f} WPM"
            if p1_wpm is not None and p2_wpm is not None
            else "-"
        )
        front_lines.extend(
            [
                "",
                f"**직전 세션 ({latest['session_date']} · {str(latest.get('track', '')).upper()})**",
                f"- 주제: {_short(latest.get('topic_prompt', ''), 80)}",
                f"- 압축 변화: {wpm_str} · 점수 {latest.get('score') if latest.get('score') is not None else '-'}",
            ]
        )
        if latest.get("native_model"):
            front_lines.append(f"- 핵심 원어민 문장: *{latest['native_model']}*")

    back_lines = ["### 최근 14회 스피킹 로그", ""]
    if not recent_sessions:
        back_lines.append("아직 완료된 세션이 없습니다. `@ankimanager_bot`에서 `/speak`로 첫 세션을 시작하세요.")
    else:
        back_lines.append("| 날짜 | 트랙 | WPM (1차->2차) | 필러 | 점수 | 주제 |")
        back_lines.append("| :--- | :--- | :--- | :--- | :--- | :--- |")
        for s in recent_sessions[:14]:
            p1_w = s.get("pass1_wpm")
            p2_w = s.get("pass2_wpm")
            wpm_cell = f"{p1_w:.0f}->{p2_w:.0f}" if p1_w is not None and p2_w is not None else "-"
            p1_f = s.get("pass1_fillers")
            p2_f = s.get("pass2_fillers")
            fill_cell = f"{p1_f}->{p2_f}" if p1_f is not None and p2_f is not None else "-"
            score_cell = f"{s['score']}" if s.get("score") is not None else "-"
            back_lines.append(
                f"| {s['session_date']} | {s.get('track', '')} | {wpm_cell} | {fill_cell} | {score_cell} | {_short(s.get('topic_prompt', ''), 36)} |"
            )

    return {
        "앞면": "<br>".join(front_lines),
        "뒷면": "<br>".join(back_lines),
    }


class AnkiSpeakingTracker:
    """Anki `1. Language::1.1. English::Speaking` 덱에 고정 트래커 카드 1장을 두고 Due 1 <-> 0 및 로그를 제어한다."""

    def __init__(self, invoke: Optional[Callable[..., Any]] = None) -> None:
        self._invoke = invoke or AnkiConnector.invoke

    def _ensure_tracker_note_and_card(self) -> tuple[int, int]:
        self._invoke("createDeck", deck=SPEAKING_DECK)
        note_ids = self._invoke("findNotes", query=f"tag:{TRACKER_TAG}") or []
        if not note_ids:
            note_id = self._invoke(
                "addNote",
                note={
                    "deckName": SPEAKING_DECK,
                    "modelName": TRACKER_MODEL,
                    "fields": {
                        "앞면": TRACKER_FRONT,
                        "소주제": "Daily Speaking",
                        "대주제": "English",
                        "뒷면": TRACKER_BACK,
                        "기타": "Auto-managed by Anki Manager speaking tracker",
                        "소리": "",
                    },
                    "options": {"allowDuplicate": True},
                    "tags": [TRACKER_TAG],
                },
            )
            note_ids = [note_id]

        note_id = int(note_ids[0])
        cards = self._invoke("findCards", query=f"nid:{note_id}") or []
        if not cards:
            raise RuntimeError(f"트래커 노트({note_id})에 연결된 카드를 찾을 수 없습니다.")
        return note_id, int(cards[0])

    def ensure_tracker_card(self) -> int:
        _, card_id = self._ensure_tracker_note_and_card()
        return card_id

    def reset_daily(self) -> Dict[str, Any]:
        """매일 새벽 04:05 호출: 트래커 카드를 오늘 Due(1)로 세팅한다."""
        card_id = self.ensure_tracker_card()
        self._invoke("unsuspend", cards=[card_id])
        self._invoke("setDueDate", cards=[card_id], days="0")
        return {"card_id": card_id, "due_days": "0"}

    def mark_done(self) -> Dict[str, Any]:
        """스피킹 3/3 완료 시 호출: 트래커 카드를 내일(1일 뒤)로 넘겨 오늘 Due를 0으로 만든다."""
        card_id = self.ensure_tracker_card()
        self._invoke("setDueDate", cards=[card_id], days="1")
        return {"card_id": card_id, "due_days": "1"}

    def update_log(
        self,
        streaks: Dict[str, Any],
        recent_14d: Dict[str, Any],
        recent_sessions: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """고정 트래커 노트 1장의 앞·뒷면을 최신 스트릭·WPM·최근 14회 로그로 갱신한다."""
        note_id, _ = self._ensure_tracker_note_and_card()
        fields = format_tracker_fields(streaks, recent_14d, recent_sessions)
        self._invoke("updateNoteFields", note={"id": note_id, "fields": fields})
        return {"note_id": note_id, "sessions_logged": len(recent_sessions[:14])}


def fetch_mission_vocab(
    count: int = 3,
    invoke: Optional[Callable[..., Any]] = None,
    rng: Optional[random.Random] = None,
) -> List[Dict[str, str]]:
    """Anki English Vocabulary에서 최근 추가되었거나 자주 틀리는(lapses>=4) 표현을 뽑아 보너스 미션으로 제공한다."""
    inv = invoke or AnkiConnector.invoke
    r = rng or random
    try:
        # 최근 30일 추가 또는 lapses>=4 취약 어휘 우선
        note_ids = inv(
            "findNotes",
            query='note:"English Vocabulary" (added:30 OR prop:lapses>=4) -is:suspended',
        ) or []
        if not note_ids:
            note_ids = inv("findNotes", query='note:"English Vocabulary" -is:suspended') or []
        if not note_ids:
            return []

        sample_ids = r.sample(note_ids, min(len(note_ids), max(count * 3, 6)))
        notes = inv("notesInfo", notes=sample_ids) or []
        items: List[Dict[str, str]] = []
        for n in notes:
            fields = n.get("fields") or {}
            word = _clean_field((fields.get("단어") or {}).get("value", ""))
            meaning = _clean_field((fields.get("뜻") or {}).get("value", ""))
            if word and len(word) <= 60:
                items.append({"word": word, "meaning": meaning})
            if len(items) >= count:
                break
        return items
    except Exception as e:
        logger.warning("Failed to fetch mission vocab from Anki: %s", e)
        return []
