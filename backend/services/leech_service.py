"""Leech(만성 오답) 단어 처리: 단어별 처리 방법 추천과 일괄 실행.

처리 방법
- review_today: 오늘 다시 복습 (setDueDate "0" — 학습 기록·FSRS 기억 상태 유지)
- reset: 새 카드로 초기화 (forgetCards — 학습 기록이 끊긴다)
- examples: AI 예문을 만들어 Sentence 덱에 추가하고 단어에 연결
- promote: 청크 승격 — 후보를 보고 사용자가 골라야 하므로 일괄 실행하지 않는다 (화면에서 하나씩)
- skip: 이번에는 손대지 않음

보류(suspend)는 없다: 희귀·전공 단어도 외워야 하므로 문맥(예문)을 더하는 쪽으로 추천한다.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, Literal

from core.batch_generator import BatchSentenceGenerator
from integrations.anki_connect import AnkiConnector

Action = Literal["review_today", "reset", "examples", "promote", "skip"]
ACTIONS: tuple[str, ...] = ("review_today", "reset", "examples", "promote", "skip")
ACTION_LABELS = {"review_today": "다시 학습", "reset": "초기화", "examples": "예문 추가", "promote": "청크 승격", "skip": "건너뛰기"}

BACKUP_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "backups" / "leech"
COMMON_TIERS = {"freq::tier1_essential", "freq::tier2_common"}
PROMOTE_MIN_LAPSES = 10
FEW_LINKS = 1
_PLACEHOLDER = re.compile(r"\b(A|B|C|V|V-ing)\b")


def _is_single_word(word: str) -> bool:
    w = word.strip()
    return bool(w) and " " not in w and not _PLACEHOLDER.search(w)


PROMOTABLE_POS = {"v", "adj", "adv"}


def _promotable_pos(pos: str | None) -> bool:
    # 품사가 비어 있으면 판단을 막지 않는다. 'n, v' 처럼 여러 개면 하나라도 맞으면 된다.
    if not pos or not pos.strip():
        return True
    return any(p.strip() in PROMOTABLE_POS for p in pos.split(","))


def suggest_action(*, word: str, lapses: int, link_count: int, tier: str | None, pos: str | None = None) -> dict[str, str]:
    """처리 방법 추천 (사용자가 바꿀 수 있는 기본값).

    승격은 쓰임이 여러 갈래인 동사·형용사·부사 단일어에만 추천한다 (명사는 청크 효과가 약하다).
    """
    if _is_single_word(word) and _promotable_pos(pos) and tier in COMMON_TIERS and lapses >= PROMOTE_MIN_LAPSES:
        return {"action": "promote", "reason": f"자주 쓰는 단어인데 {lapses}회 오답 → 쓰임이 분명한 청크로 바꾸기"}
    if link_count <= FEW_LINKS:
        return {"action": "examples", "reason": f"이 단어가 나오는 문장 카드 {link_count}개 → 예문으로 문맥 보강"}
    return {"action": "review_today", "reason": f"문장 카드 {link_count}개로 문맥은 있음 → 오늘 다시 복습"}


def _cards_by_note(note_ids: list[int]) -> dict[int, list[int]]:
    if not note_ids:
        return {}
    return {n["noteId"]: list(n.get("cards", [])) for n in AnkiConnector.invoke("notesInfo", notes=note_ids) or []}


def _backup(cards: list[int], items: list[dict[str, Any]]) -> Path:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    keep = ("cardId", "deckName", "interval", "factor", "reps", "lapses", "due", "type", "queue", "left", "mod")
    info = AnkiConnector.invoke("cardsInfo", cards=cards) or []
    path = BACKUP_DIR / f"leech_{time.strftime('%Y%m%d_%H%M%S')}.json"
    path.write_text(
        json.dumps({"items": items, "cards": [{k: c.get(k) for k in keep} for c in info]}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path


def apply_actions(items: list[dict[str, Any]], emit=lambda msg, progress=None: None, check_cancel=lambda: None) -> dict[str, int]:
    """review_today / reset / examples 를 실행한다. promote 는 건너뛴다 (화면에서 개별 처리)."""
    by_action: dict[str, list[dict[str, Any]]] = {a: [] for a in ACTIONS}
    for it in items:
        by_action[it["action"]].append(it)

    sched_items = by_action["review_today"] + by_action["reset"]
    cards = _cards_by_note([it["note_id"] for it in sched_items])

    # 1. 스케줄을 바꾸기 전에 카드 상태를 백업한다. 실패하면 아무것도 바꾸지 않는다.
    if sched_items:
        all_cards = [c for it in sched_items for c in cards.get(it["note_id"], [])]
        path = _backup(all_cards, sched_items)
        emit(f"카드 {len(all_cards)}장 상태 백업: {path.name}", 30)

    check_cancel()
    review_cards = [c for it in by_action["review_today"] for c in cards.get(it["note_id"], [])]
    if review_cards:
        AnkiConnector.invoke("setDueDate", cards=review_cards, days="0")
        emit(f"다시 학습: 단어 {len(by_action['review_today'])}개 (카드 {len(review_cards)}장) 오늘 복습으로", 50)

    reset_cards = [c for it in by_action["reset"] for c in cards.get(it["note_id"], [])]
    if reset_cards:
        AnkiConnector.invoke("forgetCards", cards=reset_cards)
        emit(f"초기화: 단어 {len(by_action['reset'])}개 (카드 {len(reset_cards)}장) 새 카드로", 60)

    check_cancel()
    created = 0
    if by_action["examples"]:
        emit(f"예문 생성 중: 단어 {len(by_action['examples'])}개 (Gemini)", 70)
        words = [{"note_id": it["note_id"], "word": it["word"], "meaning": it.get("meaning", "")} for it in by_action["examples"]]
        res = BatchSentenceGenerator().generate_and_add_sentences(words_data=words, generate_audio=True)
        created = int(res.get("created_count", 0))
        emit(f"예문 추가: 문장 {created}개 생성", 90)

    return {
        "review_today": len(by_action["review_today"]),
        "reset": len(by_action["reset"]),
        "examples": len(by_action["examples"]),
        "skip": len(by_action["skip"]),
        "sentences_created": created,
    }
