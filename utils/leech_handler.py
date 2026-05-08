import json
import concurrent.futures
from google import genai
from google.genai import types
from integrations.anki_connect import AnkiConnector
from utils.cli_selector import InteractiveSelector
from utils.ui import UI
from config import (
    MODEL_VOCAB, NOTE_COMPLETOR_MODEL, GEMINI_DEFAULT_TEMPERATURE,
    DECK_SENTENCE, MODEL_SENTENCE
)

class LeechHandler:
    def __init__(self):
        from dotenv import load_dotenv
        import os
        load_dotenv()
        self.client = genai.Client(api_key=os.environ.get("GOOGLE_API_KEY"))
        self.model_id = NOTE_COMPLETOR_MODEL

    def get_top_leeches(self, limit=10):
        """복습 횟수 대비 실패율이 높은(Leech) 카드를 추출"""
        # lapses >= 3 인 카드 검색
        query = f'"note:{MODEL_VOCAB}" lapses:3'
        card_ids = AnkiConnector.invoke("findCards", query=query)
        
        if not card_ids:
            return []
            
        cards_info = AnkiConnector.invoke("cardsInfo", cards=card_ids)
        
        leeches = []
        for c in cards_info:
            fields = c['fields']
            word = fields['단어']['value']
            meaning = fields['뜻']['value']
            
            leeches.append({
                "cardId": c['cardId'],
                "word": word,
                "meaning": meaning,
                "lapses": c['lapses'],
                "reviews": c['reps']
            })
            
        # 실패 횟수 순으로 정렬
        return sorted(leeches, key=lambda x: x['lapses'], reverse=True)[:limit]

    def _generate(self, prompt):
        try:
            response = self.client.models.generate_content(
                model=self.model_id,
                contents=[prompt],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=GEMINI_DEFAULT_TEMPERATURE
                )
            )
            return json.loads(response.text)
        except Exception as e:
            UI.error(f"AI 분석 실패: {e}")
            return None

    def analyze_leech(self, word, meaning):
        prompt = f"""
        당신은 전문 영어 강사입니다. 학생이 단어 '{word}'(뜻: {meaning})를 계속해서 틀리고 있습니다.
        이 단어에 대해 다음 자료를 JSON 형식으로 생성하세요.

        1. analysis_report: 이 단어가 왜 헷갈리는지, 어떤 점을 주의해야 하는지에 대한 짧고 명쾌한 한글 분석 (콘솔 출력용).
        2. sentences: 이 단어가 포함된 자연스러운 영어 문장 3개와 그에 대한 한글 번역(직역이 아닌, 자연스럽고 간결한 한국어 번역).

        [출력 지침]:
        - '해설' 필드에는 문장 자체의 의미를 설명하는 문구(예: ~라는 의미입니다, ~를 나타냅니다 등)를 절대 넣지 마십시오.
        - 대신, 문장의 자연스러운 한국어 번역 결과만 직접적으로 작성하십시오.
        - 문장은 학생이 실제 상황에서 바로 활용할 수 있는 실용적인 예시로 작성하십시오.

        [출력 형식 JSON]:
        {{
            "analysis_report": "...",
            "sentences": [
                {{"문장": "...", "해설": "..."}},
                {{"문장": "...", "해설": "..."}},
                {{"문장": "...", "해설": "..."}}
            ]
        }}
        """
        return self._generate(prompt)

    def process_selected_leech(self, leech_data):
        word = leech_data['word']
        meaning = leech_data['meaning']
        
        UI.info(f"🧠 {word} 분석 및 보강 카드 생성 중...")
        res = self.analyze_leech(word, meaning)
        if not res: return False

        # 1. Console Report
        print(f"\n[📊 Leech Analysis: {word}]")
        print(f"💡 분석: {res['analysis_report']}\n")

        # 2. Add 3 Supplementary Sentences & Schedule for tomorrow
        new_note_ids = []
        for s in res['sentences']:
            try:
                nid = AnkiConnector.add_note(DECK_SENTENCE, MODEL_SENTENCE, {"문장": s['문장'], "해설": s['해설']})
                new_note_ids.append(nid)
            except: pass
            
        if new_note_ids:
            # Get card IDs for the new notes
            new_card_ids = []
            for nid in new_note_ids:
                cids = AnkiConnector.invoke("findCards", query=f"nid:{nid}")
                new_card_ids.extend(cids)
            
            if new_card_ids:
                # Schedule for tomorrow (Interval: 1 day)
                # AnkiConnect setSpecificDueDate sets the due date. 
                # For tomorrow, we can use 1 (relative to today).
                try:
                    AnkiConnector.invoke("setSpecificDueDate", cards=new_card_ids, days=1)
                except Exception as e:
                    UI.error(f"스케줄링 실패: {e}")

        # 3. Reset original card to New
        AnkiConnector.invoke("forgetCards", cards=[leech_data['cardId']])
        
        UI.success(f"✅ {word} 처리 완료: 리포트 출력, 문장 3개 추가(내일 학습 예약), 기존 카드 초기화.")
        return True

def run_leech_reinforcement():
    handler = LeechHandler()
    UI.header("Leech Reinforcement Workflow")
    
    leeches = handler.get_top_leeches(limit=20)
    if not leeches:
        UI.info("현저하게 많이 틀리는(Leech) 카드가 없습니다.")
        return

    # User Selection
    options = [f"{l['word']} ({l['meaning']}) - Lapses: {l['lapses']}" for l in leeches]
    selector = InteractiveSelector(options, title="🎯 Reinforce Leeches (Enter: Select, C: Confirm)")
    selected_indices = selector.run_indices()
    
    if not selected_indices:
        UI.info("선택된 카드가 없습니다.")
        return

    selected_leeches = [leeches[i] for i in selected_indices]
    
    UI.info(f"총 {len(selected_leeches)}개의 카드를 보강합니다.")
    
    success_count = 0
    for l in selected_leeches:
        if handler.process_selected_leech(l):
            success_count += 1
            
    UI.header("Workflow Completed")
    UI.success(f"총 {success_count}개의 Leech 카드를 마스터했습니다!")
