import json
import re
import requests
import os
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")

from config import (
    ANKI_URL, MODEL_VOCAB, CANDIDATES_FILE, SELECTED_VOCAB_FILE, VOCAB_SELECTOR_MODEL,
    VOCAB_SELECTOR_SYS_INSTRUCT, VOCAB_SELECTOR_EXISTING_LIST_LIMIT,
    VOCAB_SELECTOR_CONTENT_LIMIT, GEMINI_DEFAULT_TEMPERATURE,
    PROGRESS_BAR_CHUNK_UPDATE_FRACTION, PROGRESS_BAR_STREAMING_LIMIT_FRACTION
)
SELECTED_FILE = SELECTED_VOCAB_FILE # for compatibility with the old code in main

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
            # This will be printed using the _print function if a pbar is provided
            # from the calling function.
            raise e

    @classmethod
    def get_existing_vocab(cls, pbar=None):
        _print(pbar, "📂 Anki 단어장 스캔 중...")
        try:
            note_ids = cls.invoke("findNotes", query=f'"note:{MODEL_VOCAB}"')
            if not note_ids: return set()
            notes_info = cls.invoke("notesInfo", notes=note_ids)
            existing = set()
            for note in notes_info:
                if '단어' in note['fields']:
                    clean = re.sub('<[^<]+?>', '', note['fields']['단어']['value']).strip().lower()
                    existing.add(clean)
            _print(pbar, f"✔️ 기존 단어 {len(existing)}개 확인.")
            return existing
        except Exception as e:
            _print(pbar, f"❌ 기존 단어 확인 중 오류: {e}")
            return set()

class VocabularySelector:
    def __init__(self, pbar=None):
        self.client = genai.Client(api_key=GOOGLE_API_KEY)
        self.model_id = VOCAB_SELECTOR_MODEL
        self.sys_instruct = VOCAB_SELECTOR_SYS_INSTRUCT
        self.pbar = pbar

    def select_vocabulary(self, text, existing_vocab):
        _print(self.pbar, "🧠 Gemini가 학습할 어휘 선별 중...")
        
        prompt = f"""
        [기존 단어 목록]:
        {list(existing_vocab)[:VOCAB_SELECTOR_EXISTING_LIST_LIMIT]}

        [전체 텍스트]:
        {text[:VOCAB_SELECTOR_CONTENT_LIMIT]}

        [지시사항]:
        TOEFL 100점 이상 수준의 학생에게 꼭 필요한, 수준 높은 학습 자료만 선별해야 합니다. 아래 [선별 예시]를 완벽하게 따라서, [전체 텍스트]에서 단어와 숙어를 선별해주십시오.

        1.  **고급 어휘/숙어 선별**:
            *   [전체 텍스트]에서 [기존 단어 목록]에 없는 단어, 명백한 숙어 (idiomatic expression) 또는 두 단어 이상으로 이루어진 구동사 (phrasal verb)를 선별합니다.
            *   **필수**: [기존 단어 목록]에 있는 어휘는 반드시 제외하십시오.
            *   **좋은 단어/숙어 (Good)**: "hit a wall", "trip most people up", "from scratch", "rule of thumb", "behind the scenes", "get the hang of", "cutting-edge"
            *   **나쁜 단어/숙어 (Bad)**: "security", "cloud", "server", "easy to start", "pretty regularly", "for example", "such as"
            *   일반적이거나, 너무 기술적이거나, 학습 가치가 낮은 표현은 제외하십시오.

        2.  **출력 형식**:
            *   결과는 "selected_vocab" (문자열 리스트) 키를 가진 JSON 객체로 반환해주십시오.
        """

        try:
            response_stream = self.client.models.generate_content_stream(
                model=self.model_id,
                contents=[self.sys_instruct, prompt],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=GEMINI_DEFAULT_TEMPERATURE
                )
            )
            
            accumulated_text = ""
            for chunk in response_stream:
                accumulated_text += chunk.text
                if self.pbar:
                    # Update gradually
                    self.pbar.update(1)

            return json.loads(accumulated_text)
        except Exception as e:
            _print(self.pbar, f"❌ AI 분석 실패: {e}")
            return None
        
def run_vocabulary_selection(data, pbar=None, step_points=0):
    """
    주어진 데이터에서 어휘를 선별합니다.

    :param data: 'source'와 'sentences' 키를 포함하는 딕셔너리
    :param pbar: tqdm progress bar instance
    :param step_points: 워크플로우에서 할당된 진행률 포인트
    :return: 선별된 어휘를 포함하는 딕셔너리 또는 None
    """
    source = data.get('source')
    sentences_data = data.get('sentences')
    
    sentences_list = []
    if isinstance(sentences_data, dict):
        sentences_list = sentences_data.get('en_sentences', [])
    elif isinstance(sentences_data, list):
        sentences_list = sentences_data
        
    content = " ".join(sentences_list)
    
    if not content:
        _print(pbar, "❌ 분석할 콘텐츠가 없습니다.")
        if pbar and step_points > 0:
            pbar.update(step_points)
        return None

    try:
        existing_vocab = AnkiManager.get_existing_vocab(pbar=pbar)
    except Exception as e:
        _print(pbar, f"❌ Anki 에러: {e}")
        existing_vocab = set() # Continue without existing vocab if Anki is not available
    
    selector = VocabularySelector(pbar=pbar)
    
    class PbarTracker:
        def __init__(self, pb, max_pts):
            self.pb = pb
            self.max_pts = max_pts
            self.used = 0
            self.amount_per_chunk = max_pts * PROGRESS_BAR_CHUNK_UPDATE_FRACTION if max_pts > 0 else 0.5
            
        def update(self):
            if not self.pb: return
            if self.used + self.amount_per_chunk <= self.max_pts * PROGRESS_BAR_STREAMING_LIMIT_FRACTION: # leave some for the end
                self.pb.update(self.amount_per_chunk)
                self.used += self.amount_per_chunk

    tracker = PbarTracker(pbar, step_points)
    
    # Temporarily monkey patch pbar to intercept the update from inside the class
    old_pbar = selector.pbar
    if selector.pbar:
        class FakePbar:
            def update(self, *args, **kwargs):
                tracker.update()
            def write(self, *args, **kwargs):
                old_pbar.write(*args, **kwargs)
        selector.pbar = FakePbar()
        
    selection = selector.select_vocabulary(content, existing_vocab)
    
    # Restore the real pbar
    selector.pbar = old_pbar
    
    if pbar and step_points > tracker.used:
        pbar.update(step_points - tracker.used)

    if selection and 'selected_vocab' in selection:
        return {
            "source": source,
            "vocab": selection["selected_vocab"]
        }
    else:
        _print(pbar, "❌ AI가 어휘를 선별하지 못했습니다. 응답: ", selection)
        return None

def main():
    print("=== Anki Vocabulary Selector ===")
    
    try:
        with open(CANDIDATES_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        print(f"📄 '{CANDIDATES_FILE}' 파일 로드 완료 (출처: {data.get('source')})")

    except FileNotFoundError:
        print(f"❌ 입력 파일 '{CANDIDATES_FILE}'을 찾을 수 없습니다. extractor.py를 먼저 실행하세요.")
        return
    except json.JSONDecodeError:
        print(f"❌ '{CANDIDATES_FILE}' 파일의 형식이 올바르지 않습니다.")
        return

    selected_data = run_vocabulary_selection(data)

    if selected_data:
        try:
            with open(SELECTED_FILE, 'w', encoding='utf-8') as f:
                json.dump(selected_data, f, ensure_ascii=False, indent=2)
            print(f"💾 선별된 어휘를 '{SELECTED_FILE}'에 저장 완료. 단어: {len(selected_data['vocab'])}")
        except IOError as e:
            print(f"❌ 파일 저장 실패: {e}")



if __name__ == "__main__":
    main()
