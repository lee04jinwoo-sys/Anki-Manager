import sys
import os
import json
import concurrent.futures

# Add current directory to path so we can import project modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from integrations.anki_connect import AnkiConnector
    from integrations.audio import AnkiTTSFiller
    from core.completer import NoteCompleter
    from config import (
        MODEL_SENTENCE, DECK_SENTENCE, 
        MODEL_VOCAB, DECK_VOCAB, 
        MODEL_GRAMMAR, DECK_GRAMMAR,
        NOTE_COMPLETOR_MAX_WORKERS
    )
    from utils.pos_automator import get_simple_pos, setup_nltk
except ImportError as e:
    print(f"❌ Import Error: {e}")
    print("Ensure you are running this script from the 'Anki Manager' directory.")
    sys.exit(1)

def bridge_add_items(items, enrich=True):
    """
    items: list of dicts. 
    Each dict should have:
    - 'model': 'Sentence', 'Vocab', or 'Grammar'
    - 'fields': dict of initial fields (e.g., {'문장': 'Hello'} or {'단어': 'Apple'})
    """
    completer = NoteCompleter()
    setup_nltk()
    
    processed_notes = []

    def process_item(item):
        model_type = item.get('model', 'Sentence')
        fields = item.get('fields', {})
        
        if 'Sentence' in model_type:
            deck, model = DECK_SENTENCE, MODEL_SENTENCE
            main_field = "문장"
            all_fields = ["문장", "해설"]
        elif 'Vocab' in model_type:
            deck, model = DECK_VOCAB, MODEL_VOCAB
            main_field = "단어"
            all_fields = ["단어", "뜻", "품사", "유의어", "예문", "설명"]
        elif 'Grammar' in model_type:
            deck, model = DECK_GRAMMAR, MODEL_GRAMMAR
            main_field = "문장"
            all_fields = ["문장", "해설", "보기1", "보기2", "보기3", "정답", "설명"]
        else:
            print(f"⚠️ Unknown model type: {model_type}")
            return None

        main_val = fields.get(main_field, "")
        if not main_val:
            return None

        # 1. Enrichment
        if enrich:
            missing = [f for f in all_fields if not fields.get(f, "").strip()]
            if missing:
                print(f"📡 Enriching {model_type}: {main_val[:20]}...")
                
                # Special handling for Vocab POS
                if 'Vocab' in model_type and "품사" in missing:
                    pos = get_simple_pos(main_val)
                    if pos:
                        fields["품사"] = pos
                        missing.remove("품사")
                
                if missing:
                    try:
                        enriched = completer.complete_fields(model, main_val, fields, missing)
                        if enriched:
                            # Handle cases where AI might wrap result in a key or return a string
                            if isinstance(enriched, dict):
                                # If it's a nested dict like {"fields": {...}}, unwrap it
                                if len(enriched) == 1 and isinstance(list(enriched.values())[0], dict):
                                    enriched = list(enriched.values())[0]
                                # 사용자가 준 필드는 그대로 두고, 비어 있던 필드만 AI 결과로 채운다.
                                fields.update({
                                    k: v for k, v in enriched.items()
                                    if k in missing and isinstance(v, str) and v.strip()
                                })
                            else:
                                print(f"⚠️ Unexpected enrichment format for {main_val[:20]}: {type(enriched)}")
                    except Exception as e:
                        print(f"⚠️ Enrichment failed for {main_val[:20]}: {e}")

        # 2. Add to Anki
        try:
            if "영상ID" in fields and model != MODEL_VOCAB:
                AnkiConnector.ensure_model_fields(model, ["영상ID", "시작시간"])
            elif model == MODEL_VOCAB:
                fields.pop("영상ID", None)
                fields.pop("시작시간", None)
            AnkiConnector.add_note(deck, model, fields)
            print(f"✅ Added {model}: {main_val[:30]}")
            return True
        except Exception as e:
            if "duplicate" in str(e).lower():
                print(f"⏭️ Duplicate skipped: {main_val[:30]}")
                return True
            else:
                print(f"❌ Failed to add {main_val[:30]}: {e}")
                return False

    with concurrent.futures.ThreadPoolExecutor(max_workers=NOTE_COMPLETOR_MAX_WORKERS) as executor:
        results = list(executor.map(process_item, items))
    
    from utils.organizer import run_organizer

    added_count = sum(1 for r in results if r)
    if added_count > 0:
        print(f"🔊 Generating audio for {added_count} items...")
        AnkiTTSFiller.run_audio_addition()

        # 중복 정리는 컬렉션 전체를 건드리므로 여기서 자동 실행하지 않는다 (웹 UI '노트 정리'에서 명시적으로 실행).
        print("🧹 Organizing cards...")
        run_organizer()

        # 휴대폰에 바로 보이도록 AnkiWeb과 동기화한다 (실패하면 텔레그램 알림, 전체 동기화는 강제하지 않음).
        from integrations import anki_sync
        print("🔄 Syncing with AnkiWeb...")
        anki_sync.sync_and_report(anki_sync.anki_connect_sync, anki_sync.telegram_notifier())

        print("✨ All tasks completed successfully.")

def main(argv):
    if len(argv) < 2:
        print("Usage: python agent_bridge.py '<json_data>' | <file> | - [enrich_boolean]")
        print("Example: python agent_bridge.py '[{\"model\": \"Sentence\", \"fields\": {\"문장\": \"I am a student.\"}}]'")
        print("서버 실행: ssh oracle-quant 'cd ~/anki-manager && .venv/bin/python agent_bridge.py -' < items.json")
        return
    try:
        source = argv[1]
        # '-'는 표준입력. SSH로 서버에서 실행할 때 따옴표가 깨지지 않게 한다.
        if source == "-":
            data = json.load(sys.stdin)
        elif os.path.isfile(source):
            with open(source, 'r') as f:
                data = json.load(f)
        else:
            data = json.loads(source)

        enrich_flag = not (len(argv) > 2 and argv[2].lower() == 'false')
        bridge_add_items(data, enrich=enrich_flag)
    except Exception as e:
        print(f"❌ Execution Error: {e}")


if __name__ == "__main__":
    main(sys.argv)
