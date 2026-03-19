from google import genai
from google.genai import types
import requests
import json
from tqdm import tqdm
import re
import os
from dotenv import load_dotenv

load_dotenv()
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")

from config import (
    ANKI_URL, DECK_SENTENCE, MODEL_SENTENCE, DECK_VOCAB, MODEL_VOCAB,
    SELECTED_SENTENCES_FILE, SELECTED_VOCAB_FILE, NOTE_COMPLETOR_MODEL,
    NOTE_COMPLETOR_SYS_INSTRUCT, GEMINI_DEFAULT_TEMPERATURE,
    NOTE_COMPLETOR_MAX_WORKERS, NOTE_ENRICH_PROGRESS_RATIO
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
            raise e

    @classmethod
    def add_notes(cls, data, pbar=None, step_points=0):
        if not data: 
            if pbar and step_points > 0:
                pbar.update(step_points)
            return True
        _print(pbar, "🚀 Anki 업데이트 중...")

        try:
            sentence_cards = cls.invoke('findNotes', query=f'"deck:{DECK_SENTENCE}"')
            vocab_cards = cls.invoke('findNotes', query=f'"deck:{DECK_VOCAB}"')
            
            existing_sentences = set()
            if sentence_cards:
                notes_info = cls.invoke('notesInfo', notes=sentence_cards)
                for note in notes_info:
                    if '문장' in note['fields']: existing_sentences.add(note['fields']['문장']['value'].strip())
                        
            existing_vocab = set()
            if vocab_cards:
                notes_info = cls.invoke('notesInfo', notes=vocab_cards)
                for note in notes_info:
                    if '단어' in note['fields']: existing_vocab.add(note['fields']['단어']['value'].strip())
            
            _print(pbar, f"✔️ 기존 노트 확인: 문장 {len(existing_sentences)}개, 단어 {len(existing_vocab)}개")

            sentences_to_add = data.get('sentences', [])
            vocab_to_add = data.get('vocab', [])
            total_items = len(sentences_to_add) + len(vocab_to_add)
            
            if total_items == 0:
                _print(pbar, "✨ 추가할 새 카드가 없습니다.")
                if pbar and step_points > 0:
                    pbar.update(step_points)
                return True

            cnt_sent, cnt_vocab, cnt_skipped = 0, 0, 0
            
            step_amount = (step_points / total_items) if (step_points > 0 and total_items > 0) else 0

            with tqdm(total=total_items, desc="Anki 노트 추가", leave=False) as inner_pbar:
                # 문장 노트 추가
                for item in sentences_to_add:
                    f_sentence = str(item.get('문장') or item.get('sentence') or "").strip()
                    inner_pbar.set_description(f"문장 확인 중: {f_sentence[:20]}...")
                    if not f_sentence:
                        inner_pbar.update(1)
                        if pbar and step_amount > 0: pbar.update(step_amount)
                        continue

                    if f_sentence in existing_sentences:
                        cnt_skipped += 1
                        inner_pbar.update(1)
                        if pbar and step_amount > 0: pbar.update(step_amount)
                        continue
                    
                    inner_pbar.set_description(f"문장 추가 중: {f_sentence[:20]}...")
                    f_translation = str(item.get('해설') or item.get('translation') or "").strip()
                    note = {"deckName": DECK_SENTENCE, "modelName": MODEL_SENTENCE, "fields": {"문장": f_sentence, "해설": f_translation}}
                    if cls.invoke('addNote', note=note) is not None:
                        cnt_sent += 1
                        existing_sentences.add(f_sentence)
                    inner_pbar.update(1)
                    if pbar and step_amount > 0: pbar.update(step_amount)
                
                # 단어 노트 추가
                for item in vocab_to_add:
                    f_word = str(item.get('단어') or item.get('word') or "").strip()
                    inner_pbar.set_description(f"단어 확인 중: {f_word[:20]}...")
                    if not f_word:
                        inner_pbar.update(1)
                        if pbar and step_amount > 0: pbar.update(step_amount)
                        continue

                    if f_word in existing_vocab:
                        cnt_skipped += 1
                        inner_pbar.update(1)
                        if pbar and step_amount > 0: pbar.update(step_amount)
                        continue
                    
                    inner_pbar.set_description(f"단어 추가 중: {f_word[:20]}...")
                    note = {
                        "deckName": DECK_VOCAB, "modelName": MODEL_VOCAB,
                        "fields": {
                            "단어": f_word, "뜻": str(item.get('뜻') or "").strip(), "품사": str(item.get('품사') or "").strip(),
                            "유의어": str(item.get('유의어') or "").strip(), "예문": str(item.get('예문') or "").strip(), "설명": str(item.get('설명') or "").strip()
                        }
                    }
                    if cls.invoke('addNote', note=note) is not None:
                        cnt_vocab += 1
                        existing_vocab.add(f_word)
                    inner_pbar.update(1)
                    if pbar and step_amount > 0: pbar.update(step_amount)

            total_added = cnt_sent + cnt_vocab
            if total_added > 0:
                _print(pbar, f"✨ 완료! 문장 {cnt_sent}개, 단어 {cnt_vocab}개 추가. (중복 {cnt_skipped}개 제외)")
            elif cnt_skipped > 0:
                _print(pbar, f"✨ 모든 카드가 이미 존재합니다. 중복 카드 {cnt_skipped}개를 건너뛰었습니다.")
            else:
                _print(pbar, "✨ 추가할 새 카드가 없습니다.")
            return True

        except Exception as e:
            _print(pbar, f"❌ Anki 에러: {e}")
            return False


class GeminiCurator:
    def __init__(self, pbar=None):
        self.client = genai.Client(api_key=GOOGLE_API_KEY)
        self.model_id = NOTE_COMPLETOR_MODEL
        self.sys_instruct = NOTE_COMPLETOR_SYS_INSTRUCT
        self.pbar = pbar

    def enrich_sentences(self, sentences):
        if not sentences:
            return []
            
        prompt = f"""
        시스템 프롬프트에 제공된 상세 규칙에 따라, 다음 문장 목록을 처리해주십시오.

        [처리할 문장 목록]:
        {sentences}

        [지시사항]:
        1. [처리할 문장 목록]에 있는 각 문장에 대해, '문장 필드 규칙'에 따라 자연스러운 한국어 번역을 제공해주십시오.
        2. 결과는 "sentences"(객체 리스트)라는 단일 키를 가진 JSON 객체로 반환해주십시오.
        """
        try:
            response = self.client.models.generate_content(
                model=self.model_id,
                contents=[self.sys_instruct, prompt],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=GEMINI_DEFAULT_TEMPERATURE
                )
            )
            data = json.loads(response.text)
            return data.get("sentences", [])
        except Exception as e:
            _print(self.pbar, f"❌ 문장 분석 실패: {e}")
            return []

    def enrich_vocab(self, vocab):
        if not vocab:
            return []
            
        prompt = f"""
        시스템 프롬프트에 제공된 상세 규칙에 따라, 다음 단어 목록을 처리해주십시오.

        [처리할 단어 목록]:
        {vocab}

        [지시사항]:
        1. [처리할 단어 목록]에 있는 각 단어에 대해, '단어 필드 규칙'에 따라 모든 필수 필드(단어, 뜻, 품사, 유의어, 예문, 설명)를 생성해주십시오.
        2. 결과는 "vocab"(객체 리스트)이라는 단일 키를 가진 JSON 객체로 반환해주십시오.
        """
        try:
            response = self.client.models.generate_content(
                model=self.model_id,
                contents=[self.sys_instruct, prompt],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=GEMINI_DEFAULT_TEMPERATURE
                )
            )
            data = json.loads(response.text)
            return data.get("vocab", [])
        except Exception as e:
            _print(self.pbar, f"❌ 어휘 분석 실패: {e}")
            return []

    def enrich_content(self, sentences, vocab):
        _print(self.pbar, f"🧠 Gemini가 단어와 문장 상세 정보 생성 중 (병렬 처리)...")
        
        import concurrent.futures
        enriched_data = {"sentences": [], "vocab": []}
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=NOTE_COMPLETOR_MAX_WORKERS) as executor:
            future_s = executor.submit(self.enrich_sentences, sentences)
            future_v = executor.submit(self.enrich_vocab, vocab)
            
            enriched_data["sentences"] = future_s.result()
            enriched_data["vocab"] = future_v.result()
            
        # 둘 다 빈 리스트면(오류 등) None 반환
        if not enriched_data["sentences"] and not enriched_data["vocab"]:
            if sentences or vocab: # 원본은 있었으나 결과가 없으면 실패
                return None
                
        return enriched_data

def run_note_completion(sentences_data, vocab_data, pbar=None, step_points=0, inspector_func=None):
    """
    문장과 어휘 목록을 받아서 내용을 보강하고 Anki에 추가합니다.

    :param sentences_data: 'sentences' 키를 포함하는 딕셔너리
    :param vocab_data: 'vocab' 키를 포함하는 딕셔너리
    :param pbar: tqdm progress bar instance
    :param step_points: 워크플로우에서 할당된 진행률 포인트
    :param inspector_func: 데이터 보강 후 Anki에 추가하기 전 데이터를 검수할 콜백 함수 (optional)
    :return: 성공 여부를 나타내는 Boolean
    """
    sentences_data = sentences_data or {}
    vocab_data = vocab_data or {}

    sentences_to_process = sentences_data.get('sentences', [])
    vocab_to_process = vocab_data.get('vocab', [])

    if not sentences_to_process and not vocab_to_process:
        _print(pbar, "ℹ️ 처리할 콘텐츠가 없습니다.")
        if pbar and step_points > 0:
            pbar.update(step_points)
        return True # Nothing to process is not an error

    _print(pbar, f"처리할 문장: {len(sentences_to_process)}개, 단어: {len(vocab_to_process)}개")
    
    # 30% of points for enriching, 70% for adding notes
    enrich_points = step_points * NOTE_ENRICH_PROGRESS_RATIO
    add_points = step_points - enrich_points

    curator = GeminiCurator(pbar=pbar)
    enriched_data = curator.enrich_content(sentences_to_process, vocab_to_process)
    
    if pbar and enrich_points > 0:
        pbar.update(enrich_points)

    if enriched_data:
        # Inspector 적용
        if inspector_func:
            enriched_data = inspector_func(enriched_data)

        try:
            return AnkiManager.add_notes(enriched_data, pbar=pbar, step_points=add_points)
        except Exception as e:
            _print(pbar, f"❌ Anki 에러: {e}")
            return False

    return False

def main():
    print("=== Anki Content Curator ===")
    
    sentences_data = {}
    vocab_data = {}
    
    try:
        with open(SELECTED_SENTENCES_FILE, 'r', encoding='utf-8') as f:
            sentences_data = json.load(f)
            print(f"📄 '{SELECTED_SENTENCES_FILE}' 파일 로드 완료.")
    except FileNotFoundError:
        print(f"ℹ️ '{SELECTED_SENTENCES_FILE}' 파일을 찾을 수 없어 건너뜁니다.")
    except json.JSONDecodeError:
        print(f"❌ '{SELECTED_SENTENCES_FILE}' 파일의 형식이 올바르지 않습니다.")

    try:
        with open(SELECTED_VOCAB_FILE, 'r', encoding='utf-8') as f:
            vocab_data = json.load(f)
            print(f"📄 '{SELECTED_VOCAB_FILE}' 파일 로드 완료.")
    except FileNotFoundError:
        print(f"ℹ️ '{SELECTED_VOCAB_FILE}' 파일을 찾을 수 없어 건너뜁니다.")
    except json.JSONDecodeError:
        print(f"❌ '{SELECTED_VOCAB_FILE}' 파일의 형식이 올바르지 않습니다.")

    if sentences_data or vocab_data:
        run_note_completion(sentences_data, vocab_data)
    else:
        print("❌ 처리할 콘텐츠가 없습니다.")


if __name__ == "__main__":
    main()
