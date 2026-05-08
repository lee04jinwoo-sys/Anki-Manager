import config
from integrations.anki_connect import AnkiConnector

def clean_duplicates():
    if not hasattr(config, 'DUPLICATE_CLEANUP_LIST') or not config.DUPLICATE_CLEANUP_LIST:
        print("⚠️ 설정된 중복 제거 대상이 없습니다.")
        return
    for target in config.DUPLICATE_CLEANUP_LIST:
        model, field = target.get("note_type"), target.get("target_field")
        print(f"🔍 중복 체크 중: [{model}] ({field} 필드)")
        note_ids = AnkiConnector.invoke("findNotes", query=f'note:"{model}"')
        if not note_ids: continue
        notes_info = AnkiConnector.get_notes_info(note_ids)
        seen, to_delete = {}, []
        for note in notes_info:
            val = note['fields'].get(field, {}).get('value', '').strip()
            if not val: continue
            if val in seen: 
                to_delete.append(note['noteId'])
            else: seen[val] = note['noteId']
        if to_delete: 
            print(f"  🗑️ 중복 {len(to_delete)}개 삭제 중...")
            AnkiConnector.invoke("deleteNotes", notes=to_delete)
            print("  ✅ 삭제 완료")
        else:
            print("  ✨ 중복 없음")

def find_leeches(note_type="English Vocabulary"):
    note_ids = AnkiConnector.invoke("findNotes", query=f'note:"{note_type}"')
    if not note_ids: return []
    # Simplified leech logic
    cards_info = AnkiConnector.invoke("cardsInfo", cards=AnkiConnector.invoke("findCards", query=f'note:"{note_type}"'))
    leeches = [c for c in cards_info if (c.get('lapses', 0) + c.get('reps', 0)) >= 8]
    leeches.sort(key=lambda x: x.get('lapses', 0) / x.get('reps', 1) if x.get('reps', 0) > 0 else 0, reverse=True)
    return leeches[:10]
