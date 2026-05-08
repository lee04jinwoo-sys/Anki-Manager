import json
import os
import re
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")

from config import (
    SITUATION_GENERATOR_MODEL, SITUATION_GENERATOR_SYS_INSTRUCT,
    SITUATION_GENERATOR_ITEM_COUNT, GEMINI_SITUATION_TEMPERATURE,
    PROGRESS_BAR_CHUNK_UPDATE_FRACTION, PROGRESS_BAR_STREAMING_LIMIT_FRACTION,
    GRAMMAR_GENERATOR_MODEL, MODEL_VOCAB
)
from integrations.anki_connect import AnkiConnector

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

    def get_existing_vocab(self):
        """기존 Anki에 있는 단어 목록을 가져옴 (중복 방지용)"""
        existing = set()
        try:
            note_ids = AnkiConnector.find_notes(query=f'"note:{MODEL_VOCAB}"')
            if note_ids:
                notes_info = AnkiConnector.get_notes_info(note_ids)
                for note in notes_info:
                    if '단어' in note['fields']:
                        clean = re.sub('<[^<]+?>', '', note['fields']['단어']['value']).strip().lower()
                        existing.add(clean)
        except Exception as e:
            _print(self.pbar, f"⚠️ 기존 어휘 로드 실패: {e}")
        return list(existing)

    def generate_for_situation(self, situation_text, count=None):
        count = count or SITUATION_GENERATOR_ITEM_COUNT
        existing_vocab = self.get_existing_vocab()
        
        _print(self.pbar, f"🧠 Gemini가 '{situation_text}' 상황에 유용한 표현 {count}개 생성 중 (중복 제외)...")
        
        prompt = f"""
        사용자가 제시한 다음 상황에 대해, 원어민들이 실제로 자주 쓰는 매우 자연스럽고 유용한 영어 문장 {count}개와 핵심 단어/숙어 {count}개를 생성해주십시오.

        [상황]: {situation_text}
        
        [이미 알고 있는 단어 목록 (제외 대상)]:
        {existing_vocab[:1500]}

        [지시사항]:
        1. [상황]과 관련하여 실생활에서 바로 쓸 수 있는 생생한 표현 위주로 구성하십시오.
        2. **[이미 알고 있는 단어 목록]에 있는 단어는 절대로 포함하지 마십시오.** 
        3. 이미 아는 단어라면, 그보다 더 격식 있거나 난이도 높은 유의어/대안 표현을 발굴하십시오.
        4. 영어 학습 중급자~고급자(TOEFL 90~100점 이상 수준)에게 도움될 만한 수준 있는 숙어(Idiom)와 구동사(Phrasal verb)를 적극 활용하십시오.
        5. 문장은 4단어 이상, 20단어 이하로 구성하십시오.
        6. 문장은 문자열 리스트로, 단어는 {{"단어": "word", "뜻": "meaning"}} 형식의 객체 리스트로 생성하십시오.
        7. "sentences" (문자열 리스트)와 "vocab" (객체 리스트) 두 개의 키를 가진 단일 JSON 객체로 반환해주십시오.
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

class GrammarGenerator:
    def __init__(self, pbar=None):
        self.client = genai.Client(api_key=GOOGLE_API_KEY)
        self.model_id = GRAMMAR_GENERATOR_MODEL
        self.pbar = pbar
        
        self.sys_instruct = """
 당신은 15년 경력의 TOEIC, TOEFL 전문 출제위원이자, 영어 회화 학습을 돕는 Anki 데이터 설계 전문가입니다.
 주어진 문법 주제와 개수에 맞춰 영문법 문제를 생성합니다.
 반드시 아래의 JSON 배열(Array of Objects) 형식으로만 응답해야 합니다.
 
 [데이터 생성 규칙]
 1. 문장: 빈칸(____)을 만들지 말고, 정답이 포함된 완벽한 전체 문장을 작성하세요.
    *중요: 문장 내에 반드시 '정답' 필드에 쓴 단어(또는 구)가 토씨 하나 안 틀리고 그대로 포함되어 있어야 합니다. (추후 JS가 이 단어를 찾아 빈칸으로 바꿀 목적입니다)
 2. 해설: 한국어로 작성하며, 왜 그것이 정답인지와 핵심 문법 포인트를 짧고 명확하게 설명하세요.
 3. 정답 및 보기: 정답 1개와 오답 3개를 생성하세요. 오답은 반드시 문법적으로 헷갈릴 만한 유효한 방해물이어야 합니다.
 4. 중복 금지: 생성되는 모든 문장은 유니크해야 합니다.
 
 [JSON 출력 형식 예시]
 [
   {
     "문장": "The complete sentence containing the correct answer goes here.",
     "해설": "이 자리는 [문법적 이유]이므로 [정답]이 적절합니다.",
     "정답": "correct answer",
     "보기1": "wrong option 1",
     "보기2": "wrong option 2",
     "보기3": "wrong option 3"
   }
 ]
 """

    def generate_questions(self, topic, count):
        _print(self.pbar, f"🧠 주제 '{topic}'에 대한 문법 문제 {count}개 생성 중...")
        
        prompt = f"주제: {topic}\n생성 개수: {count}개"
        
        try:
            response = self.client.models.generate_content(
                model=self.model_id,
                contents=[self.sys_instruct, prompt],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.7
                )
            )
            return json.loads(response.text)
        except Exception as e:
            _print(self.pbar, f"❌ 문법 생성 AI 분석 실패: {e}")
            return None

def generate_situation_content(situation_text, count=None, pbar=None, step_points=0):
    generator = SituationGenerator(pbar=pbar)
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
            def update(self, *args, **kwargs): tracker.update()
            def write(self, *args, **kwargs):
                if hasattr(old_pbar, 'write'): old_pbar.write(*args, **kwargs)
                else: print(*args, **kwargs)
        generator.pbar = FakePbar()
    result = generator.generate_for_situation(situation_text, count=count)
    generator.pbar = old_pbar
    if pbar and step_points > tracker.used:
        pbar.update(step_points - tracker.used)
    return result
