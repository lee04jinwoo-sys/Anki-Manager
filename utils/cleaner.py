import html
import re

import config
from integrations.anki_connect import AnkiConnector

DUPLICATE_TAG = "dup::review"


def _normalize(value: str) -> str:
    text = html.unescape(re.sub(r"<[^>]+>", "", value))
    return re.sub(r"\s+", " ", text).strip().lower()


def clean_duplicates():
    """중복 노트를 정리한다. 영구 삭제하지 않는다.

    같은 값(HTML·공백·대소문자 무시)을 가진 노트 중 리뷰 수가 가장 많은 노트를 남기고,
    나머지는 DUPLICATE_TAG 태그를 달아 카드를 일시정지한다. 확인 후 Anki에서 직접 지우면 된다.
    """
    if not getattr(config, "DUPLICATE_CLEANUP_LIST", None):
        print("⚠️ 설정된 중복 제거 대상이 없습니다.")
        return
    for target in config.DUPLICATE_CLEANUP_LIST:
        model, field = target.get("note_type"), target.get("target_field")
        print(f"🔍 중복 체크 중: [{model}] ({field} 필드)")
        note_ids = AnkiConnector.invoke("findNotes", query=f'note:"{model}"')
        if not note_ids:
            continue
        notes_info = AnkiConnector.invoke("notesInfo", notes=note_ids) or []

        groups: dict[str, list[dict]] = {}
        for note in notes_info:
            key = _normalize(note["fields"].get(field, {}).get("value", ""))
            if key:
                groups.setdefault(key, []).append(note)
        dup_groups = [g for g in groups.values() if len(g) > 1]
        if not dup_groups:
            print("  ✨ 중복 없음")
            continue

        card_ids = [c for g in dup_groups for n in g for c in n.get("cards", [])]
        reps = {c["cardId"]: c.get("reps", 0) for c in (AnkiConnector.invoke("cardsInfo", cards=card_ids) or [])}

        loser_notes, loser_cards = [], []
        for group in dup_groups:
            keeper = max(group, key=lambda n: sum(reps.get(c, 0) for c in n.get("cards", [])))
            for n in group:
                if n is not keeper:
                    loser_notes.append(n["noteId"])
                    loser_cards.extend(n.get("cards", []))

        print(f"  🏷️ 중복 {len(loser_notes)}개에 '{DUPLICATE_TAG}' 태그 + 일시정지 (삭제하지 않음)")
        AnkiConnector.invoke("addTags", notes=loser_notes, tags=DUPLICATE_TAG)
        if loser_cards:
            AnkiConnector.invoke("suspend", cards=loser_cards)
def find_leeches(note_type="English Vocabulary"):
    note_ids = AnkiConnector.invoke("findNotes", query=f'note:"{note_type}"')
    if not note_ids: return []
    # Simplified leech logic
    cards_info = AnkiConnector.invoke("cardsInfo", cards=AnkiConnector.invoke("findCards", query=f'note:"{note_type}"'))
    leeches = [c for c in cards_info if (c.get('lapses', 0) + c.get('reps', 0)) >= 8]
    leeches.sort(key=lambda x: x.get('lapses', 0) / x.get('reps', 1) if x.get('reps', 0) > 0 else 0, reverse=True)
    return leeches[:10]
