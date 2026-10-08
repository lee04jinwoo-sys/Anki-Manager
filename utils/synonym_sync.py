import json
import os
import re
from integrations.anki_connect import AnkiConnector
from config import USER_CONFIG_PATH, MODEL_VOCAB

def run_synonym_sync(clusters=None, old_clusters=None):
    """
    Syncs synonym clusters to Anki. 
    ALWAYS prioritizes the provided clusters to ensure clean data.
    """
    if not clusters:
        print("⚠️ 처리할 클러스터 데이터가 없습니다. (먼저 cluster.py를 실행하세요)")
        return

    # 1. Helper function to build note_id -> synonym_string map
    def build_synonym_map(cls):
        m = {}
        if not cls:
            return m
        for group in cls:
            for i, target_word in enumerate(group):
                target_id = target_word['id']
                others = [s['word'].strip() for j, s in enumerate(group) if i != j]
                m[target_id] = ", ".join(others)
        return m

    new_data_map = build_synonym_map(clusters)

    # 2. Determine which notes need checking/updating
    if old_clusters is None:
        # Full sync: Fetch all notes in Anki to compare and clear old synonyms
        print(f"🔄 총 {len(clusters)}개의 클러스터를 안키에 전체 동기화 중...")
        print(f"🔍 전체 '{MODEL_VOCAB}' 노트를 가져오는 중...")
        all_note_ids = AnkiConnector.find_notes(query=f'"note:{MODEL_VOCAB}"')
        if not all_note_ids:
            return
        print(f"🔍 전체 {len(all_note_ids)}개의 노트를 안키에서 조회 중...")
        notes_info = AnkiConnector.get_notes_info(all_note_ids)
    else:
        # Incremental sync: Compare old and new clusters to find only changed note IDs
        print(f"🔄 총 {len(clusters)}개의 클러스터를 안키에 증분 동기화 중...")
        old_data_map = build_synonym_map(old_clusters)
        
        changed_note_ids = set()
        for nid, new_val in new_data_map.items():
            if old_data_map.get(nid) != new_val:
                changed_note_ids.add(nid)
        for nid, old_val in old_data_map.items():
            if nid not in new_data_map:
                # Removed from clusters: only mark as changed if it actually had synonyms before
                if old_val:
                    changed_note_ids.add(nid)
                
        if not changed_note_ids:
            print("✅ 모든 유의어가 이미 최신 상태입니다. (변경사항 없음)")
            return
            
        print(f"🔍 변경된 노트를 안키에서 조회 중 ({len(changed_note_ids)}개)...")
        notes_info = AnkiConnector.get_notes_info(list(changed_note_ids))

    update_count = 0
    clear_count = 0
    
    print(f"🔄 변경된 유의어 필드 분석 중...")
    actions = []
    
    for n in notes_info:
        if not n or 'noteId' not in n:
            continue
        nid = n['noteId']
        old_val_raw = n['fields'].get('유의어', {}).get('value', '')
        # HTML 태그 제거 및 공백 정리
        old_val = re.sub(r'<[^>]+>', '', old_val_raw).strip()
        new_val = new_data_map.get(nid, "") # If not in a cluster, clear it
        
        if old_val != new_val:
            actions.append({
                "action": "updateNoteFields",
                "params": {
                    "note": {
                        "id": nid,
                        "fields": {"유의어": new_val}
                    }
                }
            })
            if new_val: update_count += 1
            else: clear_count += 1

    if actions:
        print(f"🚀 {len(actions)}개의 노트를 Anki에 일괄 업데이트 중...")
        try:
            AnkiConnector.invoke('multi', actions=actions)
        except Exception as e:
            print(f"⚠️ 일괄 업데이트 중 에러 발생: {e}")
            print(f"순차 업데이트로 전환합니다...")
            for action in actions:
                try:
                    AnkiConnector.invoke(action['action'], **action['params'])
                except:
                    pass

    print(f"✨ 완료: {update_count}개 업데이트, {clear_count}개 불필요 데이터 삭제.")

    if update_count == 0 and clear_count == 0:
        print(f"✅ 모든 유의어가 이미 최신 상태입니다.")

if __name__ == "__main__":
    run_synonym_sync()
