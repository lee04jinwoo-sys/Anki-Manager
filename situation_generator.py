import json
import os
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
from config import (
    SITUATION_GENERATOR_MODEL, SITUATION_GENERATOR_SYS_INSTRUCT,
    SITUATION_GENERATOR_ITEM_COUNT, GEMINI_SITUATION_TEMPERATURE,
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

class SituationGenerator:
    def __init__(self, pbar=None):
        self.client = genai.Client(api_key=GOOGLE_API_KEY)
        self.model_id = SITUATION_GENERATOR_MODEL
        self.sys_instruct = SITUATION_GENERATOR_SYS_INSTRUCT
        self.pbar = pbar

    def generate_for_situation(self, situation_text):
        _print(self.pbar, f"🧠 Gemini가 '{situation_text}' 상황에 유용한 표현 생성 중...")
        
        prompt = f"""
        사용자가 제시한 다음 상황에 대해, 원어민들이 실제로 자주 쓰는 매우 자연스럽고 유용한 영어 문장 {SITUATION_GENERATOR_ITEM_COUNT}개와 핵심 단어/숙어 {SITUATION_GENERATOR_ITEM_COUNT}개를 생성해주십시오.

        [상황]: {situation_text}

        [지시사항]:
        1. 교과서적인 딱딱한 표현보다는, 실생활에서 바로 쓸 수 있는 생생한 표현 위주로 구성하십시오.
        2. 영어 학습 중급자~고급자(TOEFL 90~100점 이상 수준)에게 도움될 만한 수준 있는 숙어(Idiom)와 구동사(Phrasal verb)를 적극 활용하십시오.
        3. 문장은 4단어 이상, 20단어 이하로 구성하십시오.
        4. "sentences"(문자열 리스트)와 "vocab"(문자열 리스트) 두 개의 키를 가진 단일 JSON 객체로 반환해주십시오.
        """

        try:
            response_stream = self.client.models.generate_content_stream(
                model=self.model_id,
                contents=[self.sys_instruct, prompt],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=GEMINI_SITUATION_TEMPERATURE
                )
            )
            accumulated_text = ""
            for chunk in response_stream:
                accumulated_text += chunk.text
                if self.pbar:
                    self.pbar.update(1)
            return json.loads(accumulated_text)
        except Exception as e:
            _print(self.pbar, f"❌ 상황 생성 AI 분석 실패: {e}")
            return None

def generate_situation_content(situation_text, pbar=None, step_points=0):
    generator = SituationGenerator(pbar=pbar)
    
    # Progress tracker wrapping similar to the selectors
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
    old_pbar = generator.pbar
    if generator.pbar:
        class FakePbar:
            def update(self, *args, **kwargs):
                tracker.update()
            def write(self, *args, **kwargs):
                if hasattr(old_pbar, 'write'):
                    old_pbar.write(*args, **kwargs)
                else:
                    print(*args, **kwargs)
        generator.pbar = FakePbar()
        
    result = generator.generate_for_situation(situation_text)
    generator.pbar = old_pbar

    if pbar and step_points > tracker.used:
        pbar.update(step_points - tracker.used)

    if result and 'sentences' in result and 'vocab' in result:
        return result
    else:
        _print(pbar, "❌ AI가 상황별 콘텐츠를 생성하지 못했습니다.")
        return None
