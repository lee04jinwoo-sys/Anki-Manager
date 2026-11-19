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


class AnkiSpeakingTracker:
    """Anki `1. Language::1.1. English::Speaking` 덱에 고정 트래커 카드 1장을 두고 Due 1 <-> 0 을 제어한다."""

    def __init__(self, invoke: Optional[Callable[..., Any]] = None) -> None:
        self._invoke = invoke or AnkiConnector.invoke

    def ensure_tracker_card(self) -> int:
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

        cards = self._invoke("findCards", query=f"nid:{note_ids[0]}") or []
        if not cards:
            raise RuntimeError(f"트래커 노트({note_ids[0]})에 연결된 카드를 찾을 수 없습니다.")
        return int(cards[0])

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
