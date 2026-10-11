import json
import os
import html
import re
import concurrent.futures
from google import genai
from google.genai import types
from dotenv import load_dotenv
from tqdm import tqdm

def normalize_vocab_placeholders(word: str) -> str:
    """
    Normalizes placeholders like someone, something, sb, sth, somebody to A, B, C.
    And doing / doing something to V-ing.
    e.g., 'spring something on someone' -> 'spring A on B'
          'prevent someone from doing something' -> 'prevent A from V-ing'
    """
    # 1. Normalize 'doing something' / 'doing sth' / 'doing' to 'V-ing'
    word = re.sub(r'\bdoing\s+(something|sth)\b', 'V-ing', word, flags=re.IGNORECASE)
    word = re.sub(r'\bdoing\b', 'V-ing', word, flags=re.IGNORECASE)
    
    # 2. Normalize 'sb', 'sth', 'someone', 'something', 'somebody', 'sbd' to A, B, C
    pattern = r'\b(someone|somebody|sb|sbd|something|sth)\b'
    placeholders = ['A', 'B', 'C']
    placeholder_idx = 0
    
    def repl(match):
        nonlocal placeholder_idx
        if placeholder_idx < len(placeholders):
            res = placeholders[placeholder_idx]
            placeholder_idx += 1
            return res
        return match.group(0)
        
    normalized = re.sub(pattern, repl, word, flags=re.IGNORECASE)
    normalized = re.sub(r'\s+', ' ', normalized).strip()
    return normalized

load_dotenv()
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
FIELD_BATCH_SIZE = 10  # 빈 필드 채우기: Gemini 1회 요청당 노트 수

from config import (
    NOTE_COMPLETOR_MODEL, NOTE_COMPLETOR_SYS_INSTRUCT, NOTE_COMPLETOR_MAX_WORKERS,
    GEMINI_DEFAULT_TEMPERATURE, DECK_SENTENCE, MODEL_SENTENCE,
    DECK_VOCAB, MODEL_VOCAB, NOTE_ENRICH_PROGRESS_RATIO
)
from integrations.anki_connect import AnkiConnector
from utils.pos_automator import get_simple_pos, setup_nltk
from utils.timestamp_matcher import find_best_timestamp

def _print(pbar, *args, **kwargs):
    if pbar:
        if hasattr(pbar, 'write'):
            pbar.write(" ".join(map(str, args)), **kwargs)
        else:
            print(*args, **kwargs)
    else:
        print(*args, **kwargs)

# Gemini가 '해설' 대신 돌려주는 이름들 (2026-10-11 실측: 'explanation')
_TRANSLATION_KEY_ALIASES = ("explanation", "translation", "번역")


def _normalize_translation_key(item):
    if isinstance(item, dict) and not item.get("해설"):
        for alias in _TRANSLATION_KEY_ALIASES:
            if item.get(alias):
                item["해설"] = item[alias]
                break


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
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=self.sys_instruct,
                    response_mime_type="application/json",
                    temperature=GEMINI_DEFAULT_TEMPERATURE
                )
            )
            try:
                # strict=False allows unescaped control characters like literal newlines inside strings
                res = json.loads(response.text, strict=False)
            except Exception as json_err:
                _print(self.pbar, f"❌ Raw AI response text:\n{response.text}")
                raise json_err
            
            # AI가 리스트를 반환한 경우 첫 번째 요소만 사용하거나 딕셔너리로 변환 시도
            if isinstance(res, list) and len(res) > 0:
                res = res[0]
            
            if not isinstance(res, dict):
                _print(self.pbar, f"⚠️ AI 응답 형식이 올바르지 않습니다 (dict 기대, {type(res)} 수신)")
                return None

            # [Fix] AI가 {'sentence': {...}} 또는 {'vocabulary': {...}} 처럼 중첩해서 주는 경우 처리
            if "sentence" in res and isinstance(res["sentence"], dict):
                res = res["sentence"]
            elif "vocabulary" in res and isinstance(res["vocabulary"], dict):
                res = res["vocabulary"]
            elif "vocab" in res and isinstance(res["vocab"], dict):
                res = res["vocab"]

            # 모든 문자열 값에 대해 HTML 엔티티 제거
            def recursive_unescape(data):
                if isinstance(data, dict):
                    return {k: recursive_unescape(v) for k, v in data.items()}
                elif isinstance(data, list):
                    return [recursive_unescape(i) for i in data]
                elif isinstance(data, str):
                    return html.unescape(data)
                return data
                
            return recursive_unescape(res)
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
            각 객체는 정확히 {{"문장": "<원문>", "해설": "<한국어 번역>"}} 형식이어야 합니다 (키 이름을 바꾸지 마세요).
            '해설' 필드에는 '~라는 의미입니다'와 같은 부연 설명 없이, 문장 자체의 자연스러운 한국어 번역 결과만 직접적으로 작성하세요.
            만약 문장에 'A, B, V' 같은 플레이스홀더가 남아있다면 이를 자연스러운 실제 상황 단어로 대체하여 문장을 완성하세요.
            
            [데이터]:
            {}
            """
            futures = [
                (executor.submit(self._generate, prompt_template.format(chunk)), chunk)
                for chunk in chunks
            ]
            for future, chunk in futures:
                res = future.result()
                if res and "sentences" in res:
                    ai_items = res["sentences"]
                    if len(ai_items) == len(chunk):
                        for original_item, ai_item in zip(chunk, ai_items):
                            ai_item['문장'] = original_item
                    for ai_item in ai_items:
                        _normalize_translation_key(ai_item)
                    all_results.extend(ai_items)
        return all_results

    def enrich_vocab(self, vocab):
        if not vocab: return []
        
        chunk_size = 10
        chunks = [vocab[i:i + chunk_size] for i in range(0, len(vocab), chunk_size)]
        all_results = []

        _print(self.pbar, f"📡 단어 보강 시작... (총 {len(vocab)}개, {len(chunks)}개 묶음)")

        with concurrent.futures.ThreadPoolExecutor(max_workers=NOTE_COMPLETOR_MAX_WORKERS) as executor:
            prompt_template = """
            다음 단어 데이터 리스트에 대해, 뜻, 품사, 예문, 설명을 포함한 JSON 객체 리스트를 'vocab' 키에 담아 반환하세요.
            이미 '뜻'이나 '단어' 정보가 있다면 이를 활용하여 내용을 완성하십시오.
            특히 '설명' 필드는 의미의 미세한 차이나 뉘앙스를 한국어로 상세히 설명해야 합니다.
            
            [데이터]:
            {}
            """
            futures = [
                (executor.submit(self._generate, prompt_template.format(chunk)), chunk)
                for chunk in chunks
            ]
            for future, chunk in futures:
                res = future.result()
                if res and "vocab" in res:
                    ai_items = res["vocab"]
                    if len(ai_items) == len(chunk):
                        for original_item, ai_item in zip(chunk, ai_items):
                            if isinstance(original_item, dict) and '단어' in original_item:
                                ai_item['단어'] = original_item['단어']
                    all_results.extend(ai_items)
        return all_results

    def complete_fields(self, model_name, main_field_value, current_fields, missing_fields):
        if "Vocabulary" in model_name:
            prompt = (
                f"모델: {model_name}\n"
                f"대상 단어: {main_field_value}\n"
                f"기존 데이터: {current_fields}\n"
                f"누락된 필드: {missing_fields}\n\n"
                f"지침 규칙에 따라 누락된 필드만 채워 JSON으로 반환하세요."
            )
        elif "Sentence" in model_name:
            prompt = (
                f"모델: {model_name}\n"
                f"대상 문장: {main_field_value}\n"
                f"누락된 필드: {missing_fields}\n\n"
                f"지침 규칙에 따라 누락된 필드(해설 등)를 채워 JSON으로 반환하세요."
            )
        elif "Grammar" in model_name:
            prompt = (
                f"모델: {model_name}\n"
                f"문장 및 정답 데이터: {current_fields}\n"
                f"누락된 필드: {missing_fields}\n\n"
                f"지시: 해설(자연스러운 한국어 번역), 설명(정답 논리적 이유), 보기1~3(중복 없는 매력적인 오답)을 생성하여 JSON으로 반환하세요."
            )
        else:
            prompt = (
                f"모델: {model_name}\n"
                f"메인 데이터: {main_field_value}\n"
                f"기존 필드: {current_fields}\n"
                f"누락 필드: {missing_fields}\n\n"
                f"누락된 필드를 생성하여 JSON으로 반환하세요."
            )
        return self._generate(prompt)

    def complete_fields_batch(self, model_name, notes):
        """노트 여러 개의 누락 필드를 한 번에 채운다 (시스템 프롬프트·지시문 반복을 줄인다).

        notes: [{"id", "main", "current", "missing"}] → {id: {필드: 값}} (응답에 없는 노트는 빠진다)
        """
        if "Grammar" in model_name:
            guide = "해설은 자연스러운 한국어 번역, 설명은 정답의 논리적 이유, 보기1~3은 정답과 겹치지 않는 매력적인 오답."
        elif "Sentence" in model_name:
            guide = "해설은 문장의 자연스러운 한국어 번역만 직접 작성."
        else:
            guide = "지침 규칙(뜻·품사·예문·설명 형식)을 그대로 따른다."
        payload = [{"id": str(n["id"]), "main": n["main"], "current": n["current"], "missing": n["missing"]} for n in notes]
        prompt = (
            f"모델: {model_name}\n"
            f"아래 노트마다 'missing'에 적힌 필드만 채우세요. {guide}\n"
            "각 노트의 id를 문자열 그대로 돌려주고, missing에 없는 필드는 쓰지 마세요.\n"
            '반환 형식: {"notes": [{"id": "<id>", "<필드명>": "<값>"}]}\n\n'
            f"[노트]:\n{json.dumps(payload, ensure_ascii=False)}"
        )
        response = self.client.models.generate_content(
            model=self.model_id,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=self.sys_instruct,
                response_mime_type="application/json",
                temperature=GEMINI_DEFAULT_TEMPERATURE,
            ),
        )
        data = json.loads(response.text, strict=False)
        items = data.get("notes", []) if isinstance(data, dict) else data
        out = {}
        for it in items or []:
            if isinstance(it, dict) and "id" in it:
                fields = {k: html.unescape(v) if isinstance(v, str) else v for k, v in it.items() if k != "id"}
                out[str(it["id"])] = fields
        return out

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
            "all_fields": ["단어", "뜻", "품사", "예문", "설명"]
        },
        MODEL_GRAMMAR: {
            "triggers": ["해설", "설명", "보기1", "보기2", "보기3"],
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
            # HTML 엔티티(예: &#x27;)를 일반 문자로 변환하여 TTS 및 가독성 개선
            fields = {k: html.unescape(v['value']) for k, v in n['fields'].items()}
            
            main_field = config["all_fields"][0]
            main_val = fields.get(main_field, "")
            
            # Normalize existing vocabulary placeholders in Anki automatically
            if model_name == MODEL_VOCAB:
                normalized_word = normalize_vocab_placeholders(main_val)
                if normalized_word != main_val:
                    AnkiConnector.update_note_fields(note_id, {"단어": normalized_word})
                    _print(pbar, f"🔄 단어 표준화 자동 변환: {main_val} -> {normalized_word}")
                    main_val = normalized_word
                    fields["단어"] = normalized_word

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
            
            current_data = {f: fields[f] for f in config["all_fields"] if fields.get(f, "").strip()}
            pending.append({"id": note_id, "main": main_val, "current": current_data, "missing": missing_fields})
            return False

        def write_updates(item, result):
            # AI가 기존 필드(단어·정답 등)까지 돌려줘도 비어 있던 필드에만 쓴다.
            updates = {
                k: v for k, v in (result or {}).items()
                if k in item["missing"] and isinstance(v, str) and v.strip()
            }
            if updates:
                AnkiConnector.update_note_fields(item["id"], updates)
                _print(pbar, f"✅ 보강 완료: {item['main'][:30]} ({', '.join(updates)})")
                return True
            return False

        def process_chunk(chunk):
            """10개를 한 번에 요청하고, 응답에서 빠졌거나 묶음이 실패한 노트만 한 개씩 다시 요청한다."""
            try:
                answers = {str(k): v for k, v in (completer.complete_fields_batch(model_name, chunk) or {}).items()}
            except Exception as e:
                _print(pbar, f"⚠️ 묶음 보강 실패, 개별 요청으로 재시도: {e}")
                answers = {}
            done = 0
            for item in chunk:
                try:
                    result = answers.get(str(item["id"]))
                    if result is None:
                        result = completer.complete_fields(model_name, item["main"], item["current"], item["missing"])
                    done += write_updates(item, result)
                except Exception as e:
                    failed.append(item["id"])
                    _print(pbar, f"❌ 보강 실패 (note {item['id']}): {e}")
            return done

        failed = []
        pending = []
        for n in notes_info:
            try:
                total_updated += process_note(n)
            except Exception as e:
                failed.append(n.get('noteId'))
                _print(pbar, f"❌ 보강 실패 (note {n.get('noteId')}): {e}")

        size = FIELD_BATCH_SIZE
        chunks = [pending[i:i + size] for i in range(0, len(pending), size)]
        if chunks:
            _print(pbar, f"⏳ AI 보강: {len(pending)}개 노트, {len(chunks)}번 요청")
        with concurrent.futures.ThreadPoolExecutor(max_workers=NOTE_COMPLETOR_MAX_WORKERS) as ex:
            total_updated += sum(ex.map(process_chunk, chunks))
        if failed:
            _print(pbar, f"⚠️ {model_name}: {len(failed)}개 노트 보강 실패 (note id: {failed[:20]})")

    _print(pbar, f"🎉 총 {total_updated}개의 카드를 보강했습니다.")
    return True

def run_note_completion(sentences_data, vocab_data, pbar=None, step_points=0, inspector_func=None):
    s_list = sentences_data.get('sentences', [])
    v_list = vocab_data.get('vocab', [])
    
    # Normalize vocabulary placeholders (e.g. someone/something -> A/B)
    for v in v_list:
        if isinstance(v, dict) and '단어' in v:
            v['단어'] = normalize_vocab_placeholders(v['단어'])

    if not s_list and not v_list:
        if pbar: pbar.update(step_points)
        return True, [], []

    # 유튜브 영상 ID가 전달된 경우 안키 필드 자동 확장 확인 및 추가
    video_id = sentences_data.get("video_id") or vocab_data.get("video_id") or ""
    segments = sentences_data.get("segments") or vocab_data.get("segments") or []
    
    if video_id:
        _print(pbar, f"🔍 Anki 모델 필드 확인 중 ('영상ID', '시작시간'...)")
        if s_list:
            AnkiConnector.ensure_model_fields(MODEL_SENTENCE, ["영상ID", "시작시간"])

    # 1. 사용자 검수 (Selector)를 데이터 보강(Enrichment) 전에 실행
    if inspector_func:
        # Wrap into a dictionary as expected by main.py's cli_inspector
        inspection_data = {"sentences": s_list, "vocab": v_list}
        inspected_data = inspector_func(inspection_data)
        s_list = inspected_data.get("sentences", [])
        v_list = inspected_data.get("vocab", [])

    completer = NoteCompleter(pbar=pbar)
    step_amt = step_points * (1.0 - NOTE_ENRICH_PROGRESS_RATIO) / 2.0
    
    # 2. 사용자가 최종 선택한 데이터만 AI로 보강 (로딩 최적화)
    enriched_s = completer.enrich_sentences(s_list) if s_list else []
    if pbar: pbar.update(step_amt)
    
    enriched_v = completer.enrich_vocab(v_list) if v_list else []
    if pbar: pbar.update(step_amt)
    
    # Now add to Anki
    step_amt = step_points * NOTE_ENRICH_PROGRESS_RATIO / (len(enriched_s) + len(enriched_v) if (len(enriched_s) + len(enriched_v)) > 0 else 1)
    
    processed_sentences = []
    processed_vocab = []
    
    for s in enriched_s:
        try:
            start_time = ""
            if video_id and segments:
                start_time = str(int(find_best_timestamp(s['문장'], segments)))
                
            fields = {
                "문장": s['문장'], 
                "해설": s['해설']
            }
            if video_id:
                fields["영상ID"] = video_id
                fields["시작시간"] = start_time
                
            AnkiConnector.add_note(DECK_SENTENCE, MODEL_SENTENCE, fields)
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
            start_time = ""
            if video_id and segments:
                start_time = str(int(find_best_timestamp(word, segments)))
                
            fields = {
                "단어": word, 
                "뜻": v['뜻'], 
                "품사": pos_tag, 
                "유의어": "", 
                "예문": v['예문'], 
                "설명": v['설명']
            }
            AnkiConnector.add_note(DECK_VOCAB, MODEL_VOCAB, fields)
            processed_vocab.append(word)
        except Exception as e:
            if "duplicate" in str(e).lower():
                _print(pbar, f"⏭️ 중복 건너뜀: {word}")
                processed_vocab.append(word)
            else:
                _print(pbar, f"❌ 추가 실패: {e}")
        if pbar: pbar.update(step_amt)
    return True, processed_sentences, processed_vocab
