import json
import os
import re
from integrations.anki_connect import AnkiConnector
from config import USER_CONFIG_PATH, MODEL_VOCAB

def run_synonym_sync(clusters=None):
    """
    Syncs synonym clusters to Anki. 
    ALWAYS prioritizes the provided clusters to ensure clean data.
    """
    if not clusters:
        print("⚠️ 처리할 클러스터 데이터가 없습니다. (먼저 cluster.py를 실행하세요)")
        return

    print(f"🔄 총 {len(clusters)}개의 클러스터를 안키에 반영 중...")

    # 1. Collect all target note IDs and their NEW content
    new_data_map = {}
    for group in clusters:
        for i, target_word in enumerate(group):
            target_id = target_word['id']
            others = [s['word'].strip() for j, s in enumerate(group) if i != j]
            new_data_map[target_id] = ", ".join(others)
    
    if not new_data_map: return

    # 2. Fetch ALL Vocabulary notes to find who needs clearing
    print(f"🔍 전체 '{MODEL_VOCAB}' 노트를 가져오는 중...")
    all_note_ids = AnkiConnector.find_notes(query=f'"note:{MODEL_VOCAB}"')
    notes_info = AnkiConnector.get_notes_info(all_note_ids)
    
    update_count = 0
    clear_count = 0
    
    print(f"🔄 유의어 필드 정리 및 업데이트 중...")
    for n in notes_info:
        nid = n['noteId']
        old_val = n['fields'].get('유의어', {}).get('value', '')
        new_val = new_data_map.get(nid, "") # If not in a cluster, clear it
        
        if old_val != new_val:
            try:
                AnkiConnector.update_note_fields(nid, {"유의어": new_val})
                if new_val: update_count += 1
                else: clear_count += 1
            except: pass

    print(f"✨ 완료: {update_count}개 업데이트, {clear_count}개 불필요 데이터 삭제.")

    if update_count == 0 and clear_count == 0:
        print(f"✅ 모든 유의어가 이미 최신 상태입니다.")

if __name__ == "__main__":
    run_synonym_sync()
