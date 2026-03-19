import json
import os
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")

from config import (
    CANDIDATES_FILE, SELECTED_SENTENCES_FILE, SENTENCE_SELECTOR_MODEL,
    SENTENCE_SELECTOR_SYS_INSTRUCT, SENTENCE_SELECTOR_CONTENT_LIMIT,
    GEMINI_DEFAULT_TEMPERATURE, PROGRESS_BAR_CHUNK_UPDATE_FRACTION,
    PROGRESS_BAR_STREAMING_LIMIT_FRACTION
)
SELECTED_FILE = SELECTED_SENTENCES_FILE # for compatibility with the old code in main

def _print(pbar, *args, **kwargs):
    if pbar:
        pbar.write(" ".join(map(str, args)), **kwargs)
    else:
        print(*args, **kwargs)

class SentenceSelector:
    def __init__(self, pbar=None):
        self.client = genai.Client(api_key=GOOGLE_API_KEY)
        self.model_id = SENTENCE_SELECTOR_MODEL
        self.sys_instruct = SENTENCE_SELECTOR_SYS_INSTRUCT
        self.pbar = pbar

    def select_sentences(self, text, num_sentences=None):
        _print(self.pbar, "🧠 Gemini가 학습할 문장 선별 중...")
        
        num_instruction = f"선별하는 문장의 수는 {num_sentences}개로 엄격히 제한합니다." if num_sentences else "선별하는 문장의 수는 내용의 질에 따라 결정하되, 무조건 많이 뽑는 것이 아니라 정말 활용 가치가 있는 문장만 엄선해야 합니다."

        prompt = f"""
        [전체 텍스트]:
        {text[:SENTENCE_SELECTOR_CONTENT_LIMIT]}

        [지시사항]:
        1.  **핵심 문장 선별**: [전체 텍스트]에서 학습 가치가 높은 문장을 선별합니다.
        2.  **선별 기준**:
            *   암기했을 때 활용 가치가 높은 문장.
            *   유용한 표현이나 관용구가 포함된 문장.
            *   4단어 이상, 20단어 이하의 문장.
        3.  **출력 형식**: 결과를 "selected_sentences" (문자열 리스트) 키를 가진 JSON 객체로 반환해주십시오.
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
            
            # Since we can't easily count chunks in advance, we will update the progress bar 
            # a little bit for each chunk, up to a maximum.
            # We'll rely on the caller to finish the progress bar if needed.
            accumulated_text = ""
            for chunk in response_stream:
                accumulated_text += chunk.text
                if self.pbar:
                    # Update by a small fraction (e.g. 0.5 points) per chunk, we don't know the exact count
                    # but this gives a nice visual effect. We'll handle exact step_points in the caller.
                    self.pbar.update(1)

            return json.loads(accumulated_text)
        except Exception as e:
            _print(self.pbar, f"❌ AI 분석 실패: {e}")
            return None

def run_sentence_selection(data, pbar=None, step_points=0, num_sentences=None):
    """
    주어진 데이터에서 문장을 선별합니다.

    :param data: 'source'와 'sentences' 키를 포함하는 딕셔너리
    :param pbar: tqdm progress bar instance
    :param step_points: 워크플로우에서 할당된 진행률 포인트
    :return: 선별된 문장을 포함하는 딕셔너리 또는 None
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

    selector = SentenceSelector(pbar=pbar)
    
    # We will pass a tracker so we don't exceed step_points
    class PbarTracker:
        def __init__(self, pb, max_pts):
            self.pb = pb
            self.max_pts = max_pts
            self.used = 0
            self.amount_per_chunk = max_pts * PROGRESS_BAR_CHUNK_UPDATE_FRACTION if max_pts > 0 else 0.5
            
        def update(self):
            if not self.pb: return
            if self.used + self.amount_per_chunk <= self.max_pts * PROGRESS_BAR_STREAMING_LIMIT_FRACTION: # leave 10% for the end
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
        
    selection = selector.select_sentences(content)
    
    # Restore the real pbar
    selector.pbar = old_pbar

    if pbar and step_points > tracker.used:
        pbar.update(step_points - tracker.used)

    if selection and 'selected_sentences' in selection:
        return {
            "source": source,
            "sentences": selection["selected_sentences"]
        }
    else:
        _print(pbar, "❌ AI가 문장을 선별하지 못했습니다. 응답: ", selection)
        return None

def main():
    print("=== Anki Sentence Selector ===")
    
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

    selected_data = run_sentence_selection(data)
    
    if selected_data:
        try:
            with open(SELECTED_FILE, 'w', encoding='utf-8') as f:
                json.dump(selected_data, f, ensure_ascii=False, indent=2)
            print(f"💾 선별된 문장을 '{SELECTED_FILE}'에 저장 완료. 문장: {len(selected_data['sentences'])}")
        except IOError as e:
            print(f"❌ 파일 저장 실패: {e}")


if __name__ == "__main__":
    main()
