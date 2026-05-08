import config
from integrations.anki_connect import AnkiConnector

def _print(pbar, *args, **kwargs):
    if pbar:
        if hasattr(pbar, 'write'): pbar.write(" ".join(map(str, args)), **kwargs)
        else: print(*args, **kwargs)
    else: print(*args, **kwargs)

def run_organizer(pbar=None, step_points=0):
    note_types = config.NOTE_TYPES_CONFIG
    all_rules = []
    for model_name, model_info in note_types.items():
        deck_assignments = model_info.get('deck_assignment', [])
        for assignment in deck_assignments:
            card_name = assignment.get('card')
            target_deck = assignment.get('target')
            if card_name and target_deck:
                query = f'note:"{model_name}" card:"{card_name}" -deck:"{target_deck}"'
                all_rules.append({"query": query, "target_deck": target_deck})
    
    rules = all_rules or getattr(config, 'ORGANIZER_RULES', [])
    if not rules:
        if pbar and step_points > 0: pbar.update(step_points)
        else: print("ℹ️ 정리할 규칙이 없습니다.")
        return True

    from tqdm import tqdm
    standalone = False
    if pbar is None:
        pbar = tqdm(total=len(rules), desc="카드 정리")
        step_points = len(rules)
        standalone = True

    step_amt = step_points / len(rules) if len(rules) > 0 else 0
    total_moved = 0
    for rule in rules:
        query, target = rule["query"], rule["target_deck"]
        try:
            card_ids = AnkiConnector.invoke('findCards', query=query)
            if card_ids:
                _print(pbar, f"📦 카드 {len(card_ids)}개 이동 중: {target}")
                AnkiConnector.invoke('changeDeck', cards=card_ids, deck=target)
                total_moved += len(card_ids)
        except Exception as e:
            _print(pbar, f"❌ 이동 실패: {e}")
        if pbar: pbar.update(step_amt)
    
    if standalone:
        pbar.close()
        if total_moved > 0: print(f"✅ 총 {total_moved}개 카드 정리 완료")
        else: print("✨ 모든 카드가 이미 제 위치에 있습니다.")
    return True
