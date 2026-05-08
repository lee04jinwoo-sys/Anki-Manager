import json
import os
import re
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")

from config import (
    SENTENCE_SELECTOR_MODEL, SENTENCE_SELECTOR_SYS_INSTRUCT, SENTENCE_SELECTOR_CONTENT_LIMIT,
    VOCAB_SELECTOR_MODEL, VOCAB_SELECTOR_SYS_INSTRUCT, VOCAB_SELECTOR_CONTENT_LIMIT,
    VOCAB_SELECTOR_EXISTING_LIST_LIMIT, DEFAULT_SELECTION_COUNT, GEMINI_DEFAULT_TEMPERATURE,
    PROGRESS_BAR_CHUNK_UPDATE_FRACTION, PROGRESS_BAR_STREAMING_LIMIT_FRACTION
)

def _print(pbar, *args, **kwargs):
    if pbar:
        if hasattr(pbar, 'write'):
            pbar.write(" ".join(map(str, args)), **kwargs)
        else:
            print(*args, **kwargs)
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
        target_count = num_sentences or DEFAULT_SELECTION_COUNT
        prompt = f"""
        [전체 텍스트]:
        {text[:SENTENCE_SELECTOR_CONTENT_LIMIT]}

        [지시사항]:
        당신은 TOEFL 100점 이상의 고득점자를 교육하는 전문 영어 강사입니다. [전체 텍스트]에서 학습 가치가 매우 높은 'Gold Standard' 문장을 {target_count}개 내외로 선별하십시오. **개수(Quantity)보다 품질(Quality)이 훨씬 중요합니다. 만약 본문에 수준 높은 문장이 부족하다면, 무리하게 개수를 채우지 말고 적은 수만 반환하십시오.**

        1.  **선별 최우선 순위 (필수 포함 요소)**:
            *   **구동사(Phrasal Verbs)** 및 **관용구(Idiomatic Expressions)**.
            *   **고급 연어(Collocations)** 및 전문적인 어휘 활용.
            *   **복잡한 구문**: 관계사절, 분사구문, 도치, 양보절(Although/Despite) 등.
            *   **문장 합성**: 짧고 단순한 문장들이 이어질 경우, 이를 원어민스러운 접속사나 분사를 사용하여 하나의 논리적이고 복잡한 문장으로 합성하여 추출하십시오.

        2.  **절대 선별 금지 (Bad Cases)**:
            *   단순 S+V+O 구조: "We tried everything", "They checked it".
            *   반복되는 단순 패턴: "We didn't know how to...", "There was no...".
            *   일반적인 대화체: "It sounds impossible", "None of it makes sense".
            *   학습자가 이미 100% 알 법한 쉬운 단어만으로 구성된 문장.

        3.  **교정**: 대소문자, 문장 부호, 오타를 완벽하게 교정하십시오.

        4.  **출력 형식**: 결과를 "selected_sentences" (문자열 리스트) 키를 가진 JSON 객체로 반환해주십시오.
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
                if self.pbar: self.pbar.update(1)
            return json.loads(accumulated_text)
        except Exception as e:
            _print(self.pbar, f"❌ AI 분석 실패: {e}")
            return None

class VocabularySelector:
    def __init__(self, pbar=None):
        self.client = genai.Client(api_key=GOOGLE_API_KEY)
        self.model_id = VOCAB_SELECTOR_MODEL
        self.sys_instruct = VOCAB_SELECTOR_SYS_INSTRUCT
        self.pbar = pbar

    def select_vocabulary(self, text, existing_vocab, num_vocab=None):
        _print(self.pbar, "🧠 Gemini가 학습할 어휘 선별 중...")
        target_count = num_vocab or DEFAULT_SELECTION_COUNT
        prompt = f"""
        [기존 단어 목록]:
        {list(existing_vocab)[:VOCAB_SELECTOR_EXISTING_LIST_LIMIT]}

        [전체 텍스트]:
        {text[:VOCAB_SELECTOR_CONTENT_LIMIT]}

        [지시사항]:
        TOEFL 100점 이상 수준의 학생에게 꼭 필요한, 수준 높은 학습 자료만 {target_count}개 내외로 선별해야 합니다.
        1.  **고급 어휘/숙어 선별**: [전체 텍스트]에서 [기존 단어 목록]에 없는 단어, 숙어, 구동사를 선별합니다.
        2.  **뜻 풀이**: 선별된 각 어휘에 대해 한국어로 명확하고 간결한 뜻을 함께 작성하십시오.
        3.  **출력 형식**: "selected_vocab" 키에 {{"단어": "word", "뜻": "meaning"}} 형태의 객체 리스트를 담은 JSON 객체로 반환해주십시오.
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
                if self.pbar: self.pbar.update(1)
            return json.loads(accumulated_text)
        except Exception as e:
            _print(self.pbar, f"❌ AI 분석 실패: {e}")
            return None

def run_sentence_selection(data, count=None, pbar=None, step_points=0):
    selector = SentenceSelector(pbar=pbar)
    class PbarTracker:
        def __init__(self, pb, max_pts):
            self.pb = pb
            self.max_pts = max_pts
            self.used = 0
            self.amount_per_chunk = max_pts * PROGRESS_BAR_CHUNK_UPDATE_FRACTION if max_pts > 0 else 0.5
        def update(self):
            if not self.pb: return
            if self.used + self.amount_per_chunk <= self.max_pts * PROGRESS_BAR_STREAMING_LIMIT_FRACTION:
                self.pb.update(self.amount_per_chunk)
                self.used += self.amount_per_chunk
    tracker = PbarTracker(pbar, step_points)
    old_pbar = selector.pbar
    if selector.pbar:
        class FakePbar:
            def update(self, *args, **kwargs): tracker.update()
            def write(self, *args, **kwargs):
                if hasattr(old_pbar, 'write'): old_pbar.write(*args, **kwargs)
                else: print(*args, **kwargs)
        selector.pbar = FakePbar()
    selection = selector.select_sentences(data.get('content'), num_sentences=count)
    selector.pbar = old_pbar
    if pbar and step_points > tracker.used: pbar.update(step_points - tracker.used)
    return {"source": data.get('source'), "sentences": selection["selected_sentences"]} if selection else None

def run_vocabulary_selection(data, existing_vocab, count=None, pbar=None, step_points=0):
    selector = VocabularySelector(pbar=pbar)
    class PbarTracker:
        def __init__(self, pb, max_pts):
            self.pb = pb
            self.max_pts = max_pts
            self.used = 0
            self.amount_per_chunk = max_pts * PROGRESS_BAR_CHUNK_UPDATE_FRACTION if max_pts > 0 else 0.5
        def update(self):
            if not self.pb: return
            if self.used + self.amount_per_chunk <= self.max_pts * PROGRESS_BAR_STREAMING_LIMIT_FRACTION:
                self.pb.update(self.amount_per_chunk)
                self.used += self.amount_per_chunk
    tracker = PbarTracker(pbar, step_points)
    old_pbar = selector.pbar
    if selector.pbar:
        class FakePbar:
            def update(self, *args, **kwargs): tracker.update()
            def write(self, *args, **kwargs):
                if hasattr(old_pbar, 'write'): old_pbar.write(*args, **kwargs)
                else: print(*args, **kwargs)
        selector.pbar = FakePbar()
    selection = selector.select_vocabulary(data.get('content'), existing_vocab, num_vocab=count)
    selector.pbar = old_pbar
    if pbar and step_points > tracker.used: pbar.update(step_points - tracker.used)
    return {"source": data.get('source'), "vocab": selection["selected_vocab"]} if selection else None
