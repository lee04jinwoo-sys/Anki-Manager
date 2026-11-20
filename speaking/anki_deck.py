"""Anki-native FSRS Speaking deck manager (`1. Language::1.1. English::Speaking`)."""
from __future__ import annotations

import html
import logging
import re
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from integrations.anki_connect import AnkiConnector
from speaking.models import DailyQuestion, QueueCounts, SpeakingCard

logger = logging.getLogger("speaking.anki_deck")

SPEAKING_DECK = "1. Language::1.1. English::Speaking"
SPEAKING_PRESET_NAME = "English Speaking"
QUESTION_MODEL = "Basic"
QUESTION_TAG = "speaking::question"
DAILY_TAG = "speaking::daily"
LEGACY_TRACKER_TAG = "speaking::tracker"

_EASE_LABELS = {1: "Again", 2: "Hard", 3: "Good", 4: "Easy"}
_HTML_TAG_RE = re.compile(r"<.*?>")
_BR_RE = re.compile(r"<br\s*/?>", re.IGNORECASE)


def _html_to_text(value: str) -> str:
    if not value:
        return ""
    text = _BR_RE.sub("\n", value)
    text = _HTML_TAG_RE.sub("", text)
    text = html.unescape(text)
    lines = [line.rstrip() for line in text.splitlines()]
    return "\n".join(lines).strip()


def _extract_topic_id(tags: Sequence[str], extra_field: str) -> str:
    for t in tags:
        if t.startswith("speaking::id::"):
            return t.split("speaking::id::", 1)[1].strip()
    m = re.search(r"topic_id=([A-Za-z0-9_-]+)", extra_field or "")
    return m.group(1) if m else ""


def _short(text: str, max_len: int = 80) -> str:
    clean = " ".join((text or "").split()).replace("|", "/")
    return clean if len(clean) <= max_len else clean[: max_len - 3] + "..."


def _format_back_log(history: Sequence[Dict[str, Any]]) -> str:
    lines = ["### 스피킹 복습 로그", ""]
    if not history:
        lines.append("아직 완료된 녹음 기록이 없습니다.")
        return "<br>".join(lines)

    latest = history[0]
    if latest.get("native_model"):
        lines.append(f"**최근 원어민 대안**: *{latest['native_model']}*")
        lines.append("")

    lines.append("| 날짜 | 평가 | 점수 | WPM | 필러 | 한 줄 요약 |")
    lines.append("| :--- | :--- | :--- | :--- | :--- | :--- |")
    for row in list(history)[:5]:
        ease_val = row.get("ease")
        ease_lbl = _EASE_LABELS.get(ease_val, str(ease_val or "-"))
        score_lbl = f"{row['score']:.1f}" if isinstance(row.get("score"), (int, float)) else "-"
        wpm_lbl = f"{row['wpm']:.0f}" if isinstance(row.get("wpm"), (int, float)) else "-"
        filler_lbl = str(row.get("filler_count", "-"))
        note_text = _short(row.get("native_model") or (row.get("feedback") or {}).get("summary") or "", 48)
        lines.append(f"| {row.get('session_date', '-')} | {ease_lbl} | {score_lbl} | {wpm_lbl} | {filler_lbl} | {note_text} |")

    return "<br>".join(lines)


def _format_question_front(q: DailyQuestion) -> str:
    bullets = "<br>".join(f"- {b}" for b in q.bullets)
    parts = [f"### {q.title}", "", q.prompt]
    if bullets:
        parts.extend(["", bullets])
    return "<br>".join(parts)


class AnkiSpeakingDeck:
    """`1. Language::1.1. English::Speaking` 덱·프리셋·시딩·오늘의 FSRS 큐·답변 기록을 관리한다."""

    def __init__(self, invoke: Optional[Callable[..., Any]] = None) -> None:
        self._invoke = invoke or AnkiConnector.invoke

    def ensure_speaking_deck_and_preset(self) -> Dict[str, Any]:
        self._invoke("createDeck", deck=SPEAKING_DECK)
        current_cfg = self._invoke("getDeckConfig", deck=SPEAKING_DECK)
        if not current_cfg:
            raise RuntimeError(f"Failed to load deck config for {SPEAKING_DECK}")

        if current_cfg.get("name") == SPEAKING_PRESET_NAME:
            preset_id = int(current_cfg["id"])
        else:
            preset_id = int(
                self._invoke(
                    "cloneDeckConfigId",
                    name=SPEAKING_PRESET_NAME,
                    cloneFrom=str(current_cfg["id"]),
                )
            )

        delays_used: List[float] = []
        base_cfg = dict(current_cfg)
        base_cfg["id"] = preset_id
        base_cfg["name"] = SPEAKING_PRESET_NAME
        base_cfg["desiredRetention"] = 0.85

        for candidate_delays in ([], [1440.0]):
            attempt_cfg = dict(base_cfg)
            attempt_cfg["new"] = {
                **dict(current_cfg.get("new") or {}),
                "perDay": 1,
                "delays": list(candidate_delays),
            }
            attempt_cfg["rev"] = {
                **dict(current_cfg.get("rev") or {}),
                "perDay": 3,
            }
            attempt_cfg["lapse"] = {
                **dict(current_cfg.get("lapse") or {}),
                "delays": list(candidate_delays),
            }
            try:
                self._invoke("saveDeckConfig", config=attempt_cfg)
                delays_used = list(candidate_delays)
                break
            except Exception as e:
                logger.warning("saveDeckConfig failed with delays=%s: %s", candidate_delays, e)
                if candidate_delays == [1440.0]:
                    raise

        self._invoke("setDeckConfigId", decks=[SPEAKING_DECK], configId=preset_id)
        return {
            "deck": SPEAKING_DECK,
            "preset_name": SPEAKING_PRESET_NAME,
            "preset_id": preset_id,
            "delays_used": delays_used,
        }

    def remove_legacy_tracker_card(self) -> int:
        note_ids = self._invoke("findNotes", query=f"tag:{LEGACY_TRACKER_TAG}") or []
        if note_ids:
            self._invoke("deleteNotes", notes=note_ids)
        return len(note_ids)

    def seed_daily_questions(self, questions: Sequence[DailyQuestion]) -> Dict[str, int]:
        self._invoke("createDeck", deck=SPEAKING_DECK)
        existing_nids = self._invoke("findNotes", query=f'tag:"{QUESTION_TAG}"') or []
        existing_ids: set[str] = set()
        if existing_nids:
            notes = self._invoke("notesInfo", notes=existing_nids) or []
            for n in notes:
                extra = ((n.get("fields") or {}).get("기타") or {}).get("value", "")
                tid = _extract_topic_id(n.get("tags") or [], extra)
                if tid:
                    existing_ids.add(tid)

        to_add = []
        skipped = 0
        for q in questions:
            if q.id in existing_ids:
                skipped += 1
                continue
            to_add.append(
                {
                    "deckName": SPEAKING_DECK,
                    "modelName": QUESTION_MODEL,
                    "fields": {
                        "앞면": _format_question_front(q),
                        "소주제": q.category,
                        "대주제": "English Speaking (Daily)",
                        "뒷면": "아직 녹음 기록 없음 — 텔레그램 스피킹 봇에서 답변하면 기록이 쌓입니다.",
                        "기타": f"topic_id={q.id}",
                        "소리": "",
                    },
                    "options": {"allowDuplicate": True},
                    "tags": [QUESTION_TAG, DAILY_TAG, f"speaking::id::{q.id}"],
                }
            )

        added = 0
        for i in range(0, len(to_add), 50):
            chunk = to_add[i : i + 50]
            res = self._invoke("addNotes", notes=chunk) or []
            added += sum(1 for nid in res if nid)

        return {"added": added, "skipped": skipped}

    def get_deck_counts(self) -> QueueCounts:
        raw = self._invoke("getDeckStats", decks=[SPEAKING_DECK]) or {}
        if not raw:
            return QueueCounts()
        stat = next(iter(raw.values())) or {}
        return QueueCounts(
            new_count=int(stat.get("new_count") or 0),
            learn_count=int(stat.get("learn_count") or 0),
            review_count=int(stat.get("review_count") or 0),
            total_in_deck=int(stat.get("total_in_deck") or 0),
        )

    def fetch_today_queue(self) -> Tuple[QueueCounts, List[SpeakingCard]]:
        counts = self.get_deck_counts()
        ordered_ids: List[int] = []
        queries = [
            (f'deck:"{SPEAKING_DECK}" is:learn -is:suspended', counts.learn_count),
            (f'deck:"{SPEAKING_DECK}" is:review is:due -is:suspended', counts.review_count),
            (f'deck:"{SPEAKING_DECK}" is:new -is:suspended', counts.new_count),
        ]
        for query, limit in queries:
            if limit <= 0:
                continue
            cids = self._invoke("findCards", query=query) or []
            for cid in cids[:limit]:
                if cid not in ordered_ids:
                    ordered_ids.append(int(cid))

        if not ordered_ids:
            return counts, []

        cards_info = self._invoke("cardsInfo", cards=ordered_ids) or []
        card_by_id = {int(c["cardId"]): c for c in cards_info if "cardId" in c}
        note_ids = list(dict.fromkeys(int(c["note"]) for c in cards_info if "note" in c))
        notes_info = self._invoke("notesInfo", notes=note_ids) or [] if note_ids else []
        note_by_id = {int(n["noteId"]): n for n in notes_info if "noteId" in n}

        result: List[SpeakingCard] = []
        for cid in ordered_ids:
            c = card_by_id.get(cid)
            if not c:
                continue
            nid = int(c["note"])
            note = note_by_id.get(nid) or {}
            fields = note.get("fields") or {}
            tags = note.get("tags") or []
            extra = (fields.get("기타") or {}).get("value", "")
            front_raw = (fields.get("앞면") or {}).get("value", "")
            prompt_text = _html_to_text(front_raw)
            title = ""
            for line in prompt_text.splitlines():
                if line.startswith("### "):
                    title = line[4:].strip()
                    break
            result.append(
                SpeakingCard(
                    card_id=cid,
                    note_id=nid,
                    topic_id=_extract_topic_id(tags, extra),
                    category=_html_to_text((fields.get("소주제") or {}).get("value", "")) or "Daily",
                    title=title,
                    prompt_text=prompt_text,
                    is_new=(c.get("type") == 0),
                    reps=int(c.get("reps") or 0),
                    interval=int(c.get("interval") or 0),
                )
            )
        return counts, result

    def answer_speaking_card(self, card_id: int, ease: int) -> None:
        if ease not in (1, 2, 3, 4):
            raise ValueError(f"Invalid Anki ease rating: {ease}")
        res = self._invoke("answerCards", answers=[{"cardId": int(card_id), "ease": int(ease)}])
        if not res or not res[0]:
            raise RuntimeError(f"AnkiConnect answerCards failed for card {card_id}")

    def update_card_back_log(self, note_id: int, history: Sequence[Dict[str, Any]]) -> None:
        back_md = _format_back_log(history)
        self._invoke("updateNoteFields", note={"id": int(note_id), "fields": {"뒷면": back_md}})
