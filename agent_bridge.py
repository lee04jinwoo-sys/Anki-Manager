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
                                fields.update(enriched)
                            else:
                                print(f"⚠️ Unexpected enrichment format for {main_val[:20]}: {type(enriched)}")
                    except Exception as e:
                        print(f"⚠️ Enrichment failed for {main_val[:20]}: {e}")

        # 2. Add to Anki
        try:
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
    
    added_count = sum(1 for r in results if r)
    if added_count > 0:
        print(f"🔊 Generating audio for {added_count} items...")
        AnkiTTSFiller.run_audio_addition()
        print("✨ All tasks completed successfully.")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        try:
            # Check if first arg is a file or a JSON string
            if os.path.isfile(sys.argv[1]):
                with open(sys.argv[1], 'r') as f:
                    data = json.load(f)
            else:
                data = json.loads(sys.argv[1])
            
            # Check for 'enrich' flag in second arg
            enrich_flag = True
            if len(sys.argv) > 2 and sys.argv[2].lower() == 'false':
                enrich_flag = False
                
            bridge_add_items(data, enrich=enrich_flag)
        except Exception as e:
            print(f"❌ Execution Error: {e}")
    else:
        print("Usage: python agent_bridge.py '<json_data>' [enrich_boolean]")
        print("Example: python agent_bridge.py '[{\"model\": \"Sentence\", \"fields\": {\"문장\": \"I am a student.\"}}]'")
