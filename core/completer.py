import json
import os
import concurrent.futures
from google import genai
from google.genai import types
from dotenv import load_dotenv
from tqdm import tqdm

load_dotenv()
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")

from config import (
    NOTE_COMPLETOR_MODEL, NOTE_COMPLETOR_SYS_INSTRUCT, NOTE_COMPLETOR_MAX_WORKERS,
    GEMINI_DEFAULT_TEMPERATURE, DECK_SENTENCE, MODEL_SENTENCE,
    DECK_VOCAB, MODEL_VOCAB, NOTE_ENRICH_PROGRESS_RATIO
)
from integrations.anki_connect import AnkiConnector
from utils.pos_automator import get_simple_pos, setup_nltk

def _print(pbar, *args, **kwargs):
    if pbar:
        if hasattr(pbar, 'write'):
            pbar.write(" ".join(map(str, args)), **kwargs)
        else:
            print(*args, **kwargs)
    else:
        print(*args, **kwargs)

class NoteCompleter:
    def __init__(self, pbar=None):
        self.client = genai.Client(api_key=GOOGLE_API_KEY)
        self.model_id = NOTE_COMPLETOR_MODEL
        self.sys_instruct = NOTE_COMPLETOR_SYS_INSTRUCT
        self.pbar = pbar

    def _generate(self, prompt):
        try:
            response = self.client.models.generate_content(
                model=self.model_id,
                contents=[self.sys_instruct, prompt],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=GEMINI_DEFAULT_TEMPERATURE
                )
            )
            return json.loads(response.text)
        except Exception as e:
            _print(self.pbar, f"❌ AI 분석 실패: {e}")
            return None

    def enrich_sentences(self, sentences):
        if not sentences: return []
        
        chunk_size = 10
        chunks = [sentences[i:i + chunk_size] for i in range(0, len(sentences), chunk_size)]
        all_results = []
        
        _print(self.pbar, f"📡 문장 보강 시작... (총 {len(sentences)}개, {len(chunks)}개 묶음)")
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=NOTE_COMPLETOR_MAX_WORKERS) as executor:
            prompt_template = """
            다음 문장들에 대해 자연스러운 한국어 번역을 포함한 JSON 객체 리스트를 'sentences' 키에 담아 반환하세요.
            '해설' 필드에는 '~라는 의미입니다'와 같은 부연 설명 없이, 문장 자체의 자연스러운 한국어 번역 결과만 직접적으로 작성하세요.
            만약 문장에 'A, B, V' 같은 플레이스홀더가 남아있다면 이를 자연스러운 실제 상황 단어로 대체하여 문장을 완성하세요.
            
            [데이터]:
            {}
            """
            future_to_chunk = {
                executor.submit(self._generate, prompt_template.format(chunk)): chunk 
                for chunk in chunks
            }
            for future in concurrent.futures.as_completed(future_to_chunk):
                res = future.result()
                if res and "sentences" in res:
                    all_results.extend(res["sentences"])
        return all_results

    def enrich_vocab(self, vocab):
        if not vocab: return []
        
        chunk_size = 10
        chunks = [vocab[i:i + chunk_size] for i in range(0, len(vocab), chunk_size)]
        all_results = []

        _print(self.pbar, f"📡 단어 보강 시작... (총 {len(vocab)}개, {len(chunks)}개 묶음)")

        with concurrent.futures.ThreadPoolExecutor(max_workers=NOTE_COMPLETOR_MAX_WORKERS) as executor:
            prompt_template = """
            다음 단어 데이터 리스트에 대해, 뜻, 품사, 유의어, 예문, 설명을 포함한 JSON 객체 리스트를 'vocab' 키에 담아 반환하세요.
            이미 '뜻'이나 '단어' 정보가 있다면 이를 활용하여 내용을 완성하십시오.
            특히 '설명' 필드는 의미의 미세한 차이나 뉘앙스를 한국어로 상세히 설명해야 합니다.
            
            [데이터]:
            {}
            """
            future_to_chunk = {
                executor.submit(self._generate, prompt_template.format(chunk)): chunk 
                for chunk in chunks
            }
            for future in concurrent.futures.as_completed(future_to_chunk):
                res = future.result()
                if res and "vocab" in res:
                    all_results.extend(res["vocab"])
        return all_results

    def complete_fields(self, model_name, main_field_value, current_fields, missing_fields):
        if "Vocabulary" in model_name:
            prompt = (
                f"모델: {model_name}\n"
                f"대상 단어: {main_field_value}\n"
                f"기존 데이터: {current_fields}\n"
                f"누락된 필드: {missing_fields}\n\n"
                f"시스템 지침에 정의된 [단어 필드 작성 규칙]을 엄격히 준수하여 누락된 필드를 채우세요.\n"
                f"특히 '설명' 필드는 반드시 ①의미 뉘앙스 정의, ②유의어 비교, ③콜로케이션 마무리라는 3단계 공식을 따라야 합니다.\n"
                f"기존 데이터와 일관성을 유지하며 JSON 형식으로 누락된 필드만 반환하세요."
            )
        elif "Sentence" in model_name:
            prompt = (
                f"모델: {model_name}\n"
                f"대상 문장: {main_field_value}\n"
                f"누락된 필드: {missing_fields}\n\n"
                f"[문장 필드 작성 규칙]에 따라 누락된 필드(해설 등)를 자연스럽게 채워 JSON으로 반환하세요.\n"
                f"특히 '해설' 필드에는 문장 자체의 의미를 설명하는 투(예: ~라는 뜻입니다)를 지양하고, 자연스러운 한국어 번역 결과만 직접적으로 작성하세요.\n"
                f"또한 문장에 'A, B, V' 등의 플레이스홀더가 있다면 반드시 실제 단어로 대체하여 자연스러운 문장으로 완성하세요."
            )
        elif "Grammar" in model_name:
            prompt = (
                f"모델: {model_name}\n"
                f"문장 및 정답 데이터: {current_fields}\n"
                f"누락된 필드: {missing_fields}\n\n"
                f"제공된 문법 문제 데이터를 바탕으로 '해설'(문장 번역)과 '설명'(정답이 정답인 이유에 대한 상세 문법 해설)을 작성하세요.\n"
                f"반드시 JSON 형식으로 반환하세요."
            )
        else:
            prompt = (
                f"모델: {model_name}\n"
                f"메인 데이터: {main_field_value}\n"
                f"기존 필드: {current_fields}\n"
                f"누락 필드: {missing_fields}\n\n"
                f"위 정보를 바탕으로 누락된 필드를 생성하여 JSON으로 반환하세요."
            )
        return self._generate(prompt)

def run_universal_field_completion(pbar=None):
    from config import MODEL_SENTENCE, MODEL_VOCAB, MODEL_GRAMMAR
    
    # 필수(Trigger) 필드 설정: 이 필드들이 비어있어야 보강 대상으로 간주함
    models_config = {
        MODEL_SENTENCE: {
            "triggers": ["해설"],
            "all_fields": ["문장", "해설"]
        },
        MODEL_VOCAB: {
            "triggers": ["뜻", "품사", "예문", "설명"],
            "all_fields": ["단어", "뜻", "품사", "유의어", "예문", "설명"]
        },
        MODEL_GRAMMAR: {
            "triggers": ["해설", "설명"],
            "all_fields": ["문장", "해설", "보기1", "보기2", "보기3", "정답", "설명"]
        }
    }
    
    completer = NoteCompleter(pbar=pbar)
    total_updated = 0
    
    for model_name, config in models_config.items():
        _print(pbar, f"🔍 {model_name} 필수 필드 검사 중...")
        
        # 필수(Trigger) 필드 중 하나라도 비어있는 카드 검색
        query_parts = [f'"{f}:"' for f in config["triggers"]]
        query = f'note:"{model_name}" (' + " OR ".join(query_parts) + ")"
        
        note_ids = AnkiConnector.find_notes(query)
        if not note_ids:
            continue
            
        notes_info = AnkiConnector.get_notes_info(note_ids)
        _print(pbar, f"💡 {len(notes_info)}개의 미완성 카드 발견.")
        
        def process_note(n):
            note_id = n['noteId']
            fields = {k: v['value'] for k, v in n['fields'].items()}
            
            # 실제로 비어있는 필드 식별 (전체 필드 대상)
            missing_fields = [f for f in config["all_fields"] if not fields.get(f, "").strip()]
            
            if not any(t in missing_fields for t in config["triggers"]):
                return False
                
            main_field = config["all_fields"][0]
            main_val = fields.get(main_field, "")
            
            # [추가] Vocabulary 모델인 경우 품사 필드 우선 처리
            if model_name == MODEL_VOCAB and "품사" in missing_fields:
                pos_tag = get_simple_pos(main_val)
                if pos_tag:
                    AnkiConnector.update_note_fields(note_id, {"품사": pos_tag})
                    missing_fields.remove("품사")
                    _print(pbar, f"✅ NLTK 품사 보강: {main_val[:20]} -> {pos_tag}")
                    if not missing_fields: # 더 이상 채울 필드가 없으면 종료
                        return True
            
            _print(pbar, f"⏳ 보강 중: {main_val[:30]}... ({', '.join(missing_fields)} 필드)")
            
            current_data = {f: fields[f] for f in config["all_fields"] if fields.get(f, "").strip()}
            
            result = completer.complete_fields(model_name, main_val, current_data, missing_fields)
            if result:
                AnkiConnector.update_note_fields(note_id, result)
                _print(pbar, f"✅ 보강 완료: {main_val[:30]}")
                return True
            return False

        with concurrent.futures.ThreadPoolExecutor(max_workers=NOTE_COMPLETOR_MAX_WORKERS) as ex:
            results = list(ex.map(process_note, notes_info))
            total_updated += sum(results)
            
    _print(pbar, f"🎉 총 {total_updated}개의 카드를 보강했습니다.")
    return True

def run_note_completion(sentences_data, vocab_data, pbar=None, step_points=0, inspector_func=None):
    s_list = sentences_data.get('sentences', [])
    v_list = vocab_data.get('vocab', [])
    
    if not s_list and not v_list:
        if pbar: pbar.update(step_points)
        return True, [], []

    completer = NoteCompleter(pbar=pbar)
    step_amt = step_points * (1.0 - NOTE_ENRICH_PROGRESS_RATIO) / 2.0
    
    enriched_s = completer.enrich_sentences(s_list) if s_list else []
    if pbar: pbar.update(step_amt)
    
    enriched_v = completer.enrich_vocab(v_list) if v_list else []
    if pbar: pbar.update(step_amt)
    
    # Final inspector check if provided
    if inspector_func:
        # Wrap into a dictionary as expected by main.py's cli_inspector
        inspection_data = {"sentences": enriched_s, "vocab": enriched_v}
        enriched_data = inspector_func(inspection_data)
        enriched_s = enriched_data.get("sentences", [])
        enriched_v = enriched_data.get("vocab", [])
    
    # Now add to Anki
    step_amt = step_points * NOTE_ENRICH_PROGRESS_RATIO / (len(enriched_s) + len(enriched_v) if (len(enriched_s) + len(enriched_v)) > 0 else 1)
    
    processed_sentences = []
    processed_vocab = []
    
    for s in enriched_s:
        try:
            AnkiConnector.add_note(DECK_SENTENCE, MODEL_SENTENCE, {"문장": s['문장'], "해설": s['해설']})
            processed_sentences.append(s['문장'])
        except Exception as e:
            if "duplicate" in str(e).lower():
                _print(pbar, f"⏭️ 중복 건너뜀: {s['문장'][:20]}...")
                processed_sentences.append(s['문장'])
            else:
                _print(pbar, f"❌ 추가 실패: {e}")
        if pbar: pbar.update(step_amt)
            
    # Ensure NLTK is ready
    setup_nltk()
    
    for v in enriched_v:
        word = v.get('단어', '').strip()
        if not word: continue
        
        # Override POS with NLTK logic
        pos_tag = get_simple_pos(word)
        
        try:
            AnkiConnector.add_note(DECK_VOCAB, MODEL_VOCAB, {
                "단어": word, "뜻": v['뜻'], "품사": pos_tag, 
                "유의어": v['유의어'], "예문": v['예문'], "설명": v['설명']
            })
            processed_vocab.append(word)
        except Exception as e:
            if "duplicate" in str(e).lower():
                _print(pbar, f"⏭️ 중복 건너뜀: {word}")
                processed_vocab.append(word)
            else:
                _print(pbar, f"❌ 추가 실패: {e}")
        if pbar: pbar.update(step_amt)
    return True, processed_sentences, processed_vocab
