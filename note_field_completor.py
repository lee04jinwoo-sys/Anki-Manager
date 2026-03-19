import requests
import json
import os
import concurrent.futures
from dotenv import load_dotenv
from google import genai
from google.genai import types
from tqdm import tqdm

# Load environment variables for API keys
load_dotenv()
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY") 

# Import Anki configuration from config.py
from config import (
    ANKI_URL, DECK_VOCAB, MODEL_VOCAB, DECK_SENTENCE, MODEL_SENTENCE, NOTE_COMPLETOR_MODEL
)

def _print(pbar, *args, **kwargs):
    if pbar:
        pbar.write(" ".join(map(str, args)), **kwargs)
    else:
        print(*args, **kwargs)


class AnkiManager:
    @staticmethod
    def invoke(action, **params):
        try:
            response = requests.post(ANKI_URL, json={"action": action, "version": 6, "params": params}).json()
            if 'error' in response and response['error']: raise Exception(response['error'])
            return response['result']
        except Exception as e:
            raise Exception(f"AnkiConnect 에러: {e}")

    @classmethod
    def find_notes(cls, query):
        _print(None, f"[*] Anki 노트 검색 중: {query}")
        return cls.invoke('findNotes', query=query)

    @classmethod
    def get_notes_info(cls, note_ids):
        if not note_ids: return []
        _print(None, f"[*] {len(note_ids)}개 노트 정보 가져오는 중...")
        return cls.invoke('notesInfo', notes=note_ids)
    
    @classmethod
    def update_note_fields(cls, note_id, fields):
        _print(None, f"[+] 노트 {note_id} 필드 업데이트 중: {fields.keys()}")
        return cls.invoke('updateNoteFields', note={'id': note_id, 'fields': fields})


class GeminiFieldCompletor:
    def __init__(self, pbar=None):
        self.client = genai.Client(api_key=GOOGLE_API_KEY)
        self.model_id = NOTE_COMPLETOR_MODEL
        self.pbar = pbar
        # System instruction will be refined later
        self.sys_instruct = """
당신은 TOEFL 100점 이상의 중급 영어 학습자를 지도하는 꼼꼼하고 전문적인 영어 강사입니다.
주어진 Anki 노트의 특정 비어있는 필드를 채우는 데 도움을 줍니다. 반드시 JSON 형식으로만 응답해야 합니다.
누락된 필드만 채우고, 기존 필드는 절대 변경하거나 반복하지 마십시오.
모든 필드에 대해 note_completor.py에 정의된 [카드 작성 규칙]과 [예시]의 문체, 설명 깊이, 문장 구조를 100% 완벽하게 모방하십시오.

[단어 필드 작성 규칙]
1. 단어: 영단어 또는 숙어 
   *중요 규칙: 목적어나 보어가 동반되는 숙어 및 동사의 경우, 명사 자리는 'A', 'B'로 표기하고, 동사 원형은 'V', 동명사는 'V-ing'로 명확히 구조화하십시오. (예: consist of A, consider V-ing)
2. 뜻: 문맥에 맞는 정확한 한글 뜻 (2개 이상 시 콤마로 구분). 
   *중요 규칙: 영어 단어에 쓰인 A, B, V, V-ing 기호를 한글 뜻에도 동일하게 매칭하십시오. (예: 'A로 구성되다', 'V하는 것을 고려하다')
   *중요 규칙: 단어가 특정 문체를 가질 경우 뜻 옆에 '(격식)', '(문예)', '(비격식)' 등의 태그를 반드시 기재하십시오.
3. 품사: n, v, adj, adv, idiom, jargon 중 택일 (2개 이상 시 'n, v' 형태로 작성)
4. 유의어: 의미가 유사한 영단어 1~4개 (콤마로 구분, 없을 경우 빈 문자열)
5. 예문: 해당 단어가 사용된 실용적이고 자연스러운 영어 문장
6. 설명: 아래 3단계 공식에 맞춰 반드시 3~5문장으로 서술할 것.
   - ① 의미 및 뉘앙스 정의: "[단어]는 '[뜻]'이라는 뜻으로/의미하며, [구체적인 뉘앙스/쓰임새]를 나타냅니다." 
     *주의: 품사가 2개 이상이거나, V-ing를 목적어로 취하는 등의 문법적 특징이 있다면 반드시 서술할 것.
   - ② 유의어 비교: "'[유의어/관련 단어]'와 유사하지만/관련되지만, [단어]는 [어떤 미묘한 차이나 강도, 쓰임새의 차이]를 의미/강조합니다."
   - ③ 콜로케이션(연어) 마무리: 마지막 문장은 반드시 "자주 쓰이는 표현으로는 '[영어표현](한글뜻)' 등이 있습니다." 또는 "'[영어표현](한글뜻)'과 같이 사용/쓰입니다." 로 끝낼 것.

[문장 필드 작성 규칙]
1. 문장: 학습 가치가 높은, 원어민이 자주 쓰는 핵심 구문
2. 해설: 문장의 자연스러운 한국어 번역
"""

    def _generate_content(self, prompt):
        try:
            response = self.client.models.generate_content(
                model=self.model_id,
                contents=[self.sys_instruct, prompt],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.3
                )
            )
            return json.loads(response.text)
        except Exception as e:
            _print(self.pbar, f"❌ 콘텐츠 생성 실패: {e}")
            return None

    def complete_vocab_fields(self, current_word, current_fields, missing_fields):
        _print(self.pbar, f"🧠 단어 '{current_word}'의 누락된 필드 ({missing_fields}) 채우는 중...")
        
        # We need the main_field value to construct the prompt correctly, but it's defined in the main() function.
        # Let's get it from the current_fields dictionary, assuming the '단어' key exists.
        main_field_key = '단어'

        prompt = f"""
        시스템 프롬프트에 제공된 단어 필드 작성 규칙에 따라, 다음 Anki 단어 노트의 누락된 필드를 채워주세요.
        기존 단어: "{current_word}"
        기존 필드: {json.dumps({k: v for k, v in current_fields.items() if k != main_field_key}, ensure_ascii=False)}
        요청된 누락 필드: {", ".join(missing_fields)}
        
        응답은 요청된 누락 필드만 포함하는 JSON 객체여야 합니다.
        예시: {{"예문": "A sample sentence.", "품사": "n"}}
        """
        return self._generate_content(prompt)
    
    def complete_sentence_fields(self, current_sentence, current_fields, missing_fields):
        _print(self.pbar, f"🧠 문장 '{current_sentence}'의 누락된 필드 ({missing_fields}) 채우는 중...")
        
        main_field_key = '문장'

        prompt = f"""
        시스템 프롬프트에 제공된 문장 필드 작성 규칙에 따라, 다음 Anki 문장 노트의 누락된 필드를 채워주세요.
        기존 문장: "{current_sentence}"
        기존 필드: {json.dumps({k: v for k, v in current_fields.items() if k != main_field_key}, ensure_ascii=False)}
        요청된 누락 필드: {", ".join(missing_fields)}
        
        응답은 요청된 누락 필드만 포함하는 JSON 객체여야 합니다.
        예시: {{"해설": "한국어 번역."}}
        """
        return self._generate_content(prompt)


def process_note(note_data, main_field, completor_method):
    note_id, fields_data, missing_fields = note_data
    current_main_field_value = fields_data.get(main_field, "")
    completed_data = completor_method(current_main_field_value, fields_data, missing_fields)
    return note_id, completed_data, missing_fields


def main(pbar=None):
    is_standalone = pbar is None
    if is_standalone:
        print("=== Anki Note Field Completor ===")
        pbar = tqdm(total=0, desc="전체 진행률", position=0, leave=True)

    try:
        anki_manager = AnkiManager()
        gemini_completor = GeminiFieldCompletor(pbar=pbar)

        target_note_types = {
            MODEL_VOCAB: {
                "deck_query": f'"deck:{DECK_VOCAB}"',
                "fields_to_check": ["예문", "품사", "뜻", "유의어", "설명"],
                "main_field": "단어",
                "completor_method": gemini_completor.complete_vocab_fields
            },
            MODEL_SENTENCE: {
                "deck_query": f'"deck:{DECK_SENTENCE}"',
                "fields_to_check": ["해설"],
                "main_field": "문장",
                "completor_method": gemini_completor.complete_sentence_fields
            }
        }

        for model_name, config in target_note_types.items():
            deck_query = config["deck_query"]
            fields_to_check = config["fields_to_check"]
            main_field = config["main_field"]
            completor_method = config["completor_method"]

            _print(pbar, f"\n[노트 유형: {model_name}] 처리 시작...")
            note_ids = anki_manager.find_notes(query=f'note:"{model_name}" {deck_query}')
            
            if not note_ids:
                _print(pbar, f"ℹ️ '{model_name}' 유형의 노트를 찾을 수 없습니다. 건너뜀.")
                continue

            notes_info = anki_manager.get_notes_info(note_ids)
            notes_to_update = []

            for note in notes_info:
                note_id = note['noteId']
                fields_data = {k: v['value'].strip() for k, v in note['fields'].items()}
                
                missing_fields = []
                for field in fields_to_check:
                    if not fields_data.get(field):
                        missing_fields.append(field)

                if "유의어" in missing_fields:
                    missing_fields.remove("유의어")
                
                if missing_fields:
                    notes_to_update.append((note_id, fields_data, missing_fields))
            
            if not notes_to_update:
                _print(pbar, f"✔️ '{model_name}' 유형에서 채울 필드가 없는 노트를 찾지 못했습니다.")
                continue

            _print(pbar, f"[!] '{model_name}' 유형에서 {len(notes_to_update)}개의 채울 필드가 있는 노트를 찾았습니다.")
            if hasattr(pbar, 'total'):
                pbar.total += len(notes_to_update)
            if hasattr(pbar, 'refresh'):
                pbar.refresh()

            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                future_to_note_data = {
                    executor.submit(process_note, note_data, main_field, completor_method): note_data
                    for note_data in notes_to_update
                }

                for future in concurrent.futures.as_completed(future_to_note_data):
                    note_id, _, missing_fields = future_to_note_data[future]
                    try:
                        _, completed_data, _ = future.result()
                        
                        if completed_data:
                            update_payload = {
                                field: completed_data[field]
                                for field in missing_fields if field in completed_data
                            }
                            if update_payload:
                                anki_manager.update_note_fields(note_id, update_payload)
                                _print(pbar, f"✅ 노트 {note_id} 필드 업데이트 성공: {update_payload.keys()}")
                            else:
                                _print(pbar, f"⚠️ 노트 {note_id}: Gemini가 요청된 필드를 생성하지 못했습니다.")
                        else:
                            _print(pbar, f"❌ 노트 {note_id}: Gemini 콘텐츠 생성 실패.")
                    except Exception as exc:
                        _print(pbar, f'❌ 노트 {note_id} 처리 중 예외 발생: {exc}')
                    finally:
                        if hasattr(pbar, 'update'):
                            pbar.update(1)

    except Exception as e:
        _print(pbar, f"❌ 전역 오류 발생: {e}")
    finally:
        if is_standalone and pbar:
            pbar.close()
            print("=== Anki Note Field Completor 종료 ===")


if __name__ == "__main__":
    main() 
