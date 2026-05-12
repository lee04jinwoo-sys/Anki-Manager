import os
import json
from datetime import datetime
from integrations.anki_connect import AnkiConnector
from config import MODEL_VOCAB
from utils.pos_automator import get_simple_pos, setup_nltk
from utils.ui import UI

def run_full_pos_migration():
    setup_nltk()
    UI.header("전체 품사 일괄 마이그레이션 (NLTK)")
    
    # 모든 Vocabulary 카드 검색
    query = f'note:"{MODEL_VOCAB}"'
    try:
        note_ids = AnkiConnector.find_notes(query)
    except Exception as e:
        UI.error(f"Anki 연결 실패: {e}")
        return

    if not note_ids:
        UI.error("업데이트할 카드가 없습니다.")
        return

    notes_info = AnkiConnector.get_notes_info(note_ids)
    UI.info(f"총 {len(notes_info)}개의 카드 마이그레이션 시작...")

    log_data = []
    updated_count = 0
    skipped_count = 0
    
    with UI.progress() as progress:
        task = progress.add_task("[cyan]전체 카드 업데이트 중...", total=len(notes_info))
        
        for n in notes_info:
            note_id = n['noteId']
            word = n['fields'].get('단어', {}).get('value', '').strip()
            old_pos = n['fields'].get('품사', {}).get('value', '').strip()
            
            if not word:
                progress.update(task, advance=1)
                continue
            
            # HTML 태그 제거
            import re
            clean_word = re.sub('<[^<]+?>', '', word)
            
            new_pos = get_simple_pos(clean_word)
            
            # 로그 기록용 데이터
            status = "UNCHANGED"
            if old_pos != new_pos:
                try:
                    AnkiConnector.update_note_fields(note_id, {"품사": new_pos})
                    status = "UPDATED"
                    updated_count += 1
                except Exception as e:
                    status = f"FAILED: {e}"
            else:
                skipped_count += 1
            
            log_data.append({
                "word": clean_word,
                "old_pos": old_pos,
                "new_pos": new_pos,
                "status": status
            })
            
            progress.update(task, advance=1)

    # 로그 파일 저장
    log_dir = os.path.join(os.path.dirname(__file__), "..", "data", "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, f"pos_migration_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    
    with open(log_file, "w", encoding="utf-8") as f:
        json.dump(log_data, f, ensure_ascii=False, indent=2)

    UI.success(f"🎉 마이그레이션 완료!")
    UI.info(f"- 업데이트됨: {updated_count}개")
    UI.info(f"- 변경 없음: {skipped_count}개")
    UI.info(f"- 상세 로그: {log_file}")
    
    return log_file

if __name__ == "__main__":
    run_full_pos_migration()
