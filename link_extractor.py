from google import genai
from google.genai import types
import requests
import json
import re
import os
from bs4 import BeautifulSoup
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.formatters import TextFormatter

# ================= [통합 설정 영역] =================
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")

ANKI_URL = "http://localhost:8765"
DECK_SENTENCE = "1. Language::1.1. English::Sentence"
MODEL_SENTENCE = "English Sentence"
DECK_VOCAB = "1. Language::1.1. English::Vocabulary"
MODEL_VOCAB = "English Vocabulary"
# =================================================

class AnkiManager:
    @staticmethod
    def invoke(action, **params):
        try:
            response = requests.post(ANKI_URL, json={"action": action, "version": 6, "params": params}).json()
            if 'error' in response and response['error']: raise Exception(response['error'])
            return response['result']
        except Exception as e:
            print(f"❌ Anki 에러 ({action}): {e}")
            return None

    @classmethod
    def get_existing_vocab(cls):
        print("📂 Anki 단어장 스캔 중...")
        try:
            note_ids = cls.invoke("findNotes", query=f'"note:{MODEL_VOCAB}"')
            if not note_ids: return set()
            notes_info = cls.invoke("notesInfo", notes=note_ids)
            existing = set()
            for note in notes_info:
                if '단어' in note['fields']:
                    clean = re.sub('<[^<]+?>', '', note['fields']['단어']['value']).strip().lower()
                    existing.add(clean)
            return existing
        except:
            return set()

    @classmethod
    def add_notes(cls, data):
        if not data: return
        print("🚀 Anki 업데이트 중...")
        cnt_sent, cnt_vocab = 0, 0

        # 1. 문장(Sentences) 추가 로직
        if 'sentences' in data:
            for item in data['sentences']:
                # 필드 값이 None인 경우 빈 문자열로 처리하고 모든 값을 문자열화함
                f_sentence = str(item.get('문장') or item.get('sentence') or "").strip()
                f_translation = str(item.get('해설') or item.get('translation') or "").strip()
                
                if not f_sentence: continue # 문장 내용이 없으면 스킵

                note = {
                    "deckName": DECK_SENTENCE, 
                    "modelName": MODEL_SENTENCE,
                    "fields": {
                        "문장": f_sentence, 
                        "해설": f_translation
                    },
                    "options": {"allowDuplicate": False}
                }
                if cls.invoke('addNote', note=note): cnt_sent += 1
        
        # 2. 단어(Vocab) 추가 로직
        if 'vocab' in data:
            for item in data['vocab']:
                # 안전하게 문자열로 변환하여 에러 방지
                note = {
                    "deckName": DECK_VOCAB, "modelName": MODEL_VOCAB,
                    "fields": {
                        "단어": str(item.get('단어') or item.get('word') or "").strip(), 
                        "뜻": str(item.get('뜻') or item.get('meaning') or "").strip(), 
                        "품사": str(item.get('품사') or item.get('pos') or "").strip(), 
                        "유의어": str(item.get('유의어') or item.get('synonyms') or "").strip(), 
                        "예문": str(item.get('예문') or item.get('example') or "").strip(),
                        "설명": str(item.get('설명') or item.get('description') or "").strip()
                    },
                    "options": {"allowDuplicate": False}
                }
                if cls.invoke('addNote', note=note): cnt_vocab += 1
        print(f"✨ 완료! (문장 {cnt_sent}개, 단어 {cnt_vocab}개 추가됨)")

class GeminiAnalyzer:
    def __init__(self):
        self.client = genai.Client(api_key=GOOGLE_API_KEY)
        self.sys_instruct = """당신은 TOEFL 100점 이상의 중급 영어 학습자를 지도하는 꼼꼼하고 전문적인 영어 강사입니다.
반드시 JSON 형식으로만 응답해야 하며, 아래의 [카드 작성 규칙]과 [예시]의 문체, 설명 깊이, 문장 구조를 100% 완벽하게 모방하십시오.

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

   [단어 생성 예시 (이 톤과 문장 구조를 무조건 따를 것)]
{
  "단어": "contract",
  "뜻": "계약, 계약서, 수축하다",
  "품사": "n, v",
  "유의어": "agreement",
  "예문": "The contract had been validly drawn up.",
  "설명": "contract는 '계약'이라는 명사 외에 '수축하다, 계약하다'라는 동사로도 쓰입니다. 명사로서의 계약은 법적 구속력을 가지는 합의를 의미하며, 동사로서의 수축은 물리적인 크기가 줄어드는 것을 의미합니다. 'agreement'와 유사하지만, contract는 법적 효력이 있는 문서화된 합의를 강조합니다. 'sign a contract(계약서에 서명하다)'와 같이 사용됩니다."
},
{
  "단어": "consider V-ing",
  "뜻": "V하는 것을 고려하다",
  "품사": "v",
  "유의어": "contemplate",
  "예문": "We are considering buying a new car.",
  "설명": "'consider V-ing'는 'V하는 것을 고려하다'라는 뜻으로, 앞으로의 행동이나 계획에 대해 깊이 생각해보는 것을 의미합니다. 목적어로 to부정사가 아닌 동명사(V-ing)를 취하는 것이 중요한 문법적 특징입니다. 'think about'과 관련되지만, consider는 좀 더 진지하고 신중하게 결정을 내리기 위해 검토하는 뉘앙스를 강조합니다. 'seriously consider V-ing(진지하게 V하는 것을 고려하다)' 등이 있습니다."
},
{
  "단어": "many a A",
  "뜻": "(문예) 많은 A",
  "품사": "idiom",
  "유의어": "a great many, numerous",
  "예문": "Many a time I have wished I could fly.",
  "설명": "'many a'는 명사 앞에 쓰여 '많은'이라는 의미를 강조하는 (문예)적 표현입니다. 문법적으로는 뒤에 단수 명사가 오며 단수 취급하여 단수 동사와 함께 사용됩니다. 이는 개별적인 것들이 모여 많다는 뉘앙스를 주며, 'a great many'나 'numerous'와 유사하지만, 'many a'는 좀 더 문학적이거나 격식 있는 문맥에서 사용될 수 있습니다. 'Many a time(여러 번)'과 같이 시간의 반복을 강조할 때 자주 쓰입니다."
}

[문장 필드 작성 규칙]
1. 문장: 학습 가치가 높은, 원어민이 자주 쓰는 핵심 구문
2. 해설: 문장의 자연스러운 한국어 번역
"""

    def analyze(self, text, existing_vocab=None, prompt_rule_override=None):
        print(f"🧠 Gemini 분석 중...")
        exclude_list = list(existing_vocab or set())[:500]
        
        if prompt_rule_override:
            prompt_rule = prompt_rule_override
        else:
            prompt_rule = """
            [추출 기준 - 전문 영어 강사 모드]:
            1. 문장: 너무 간단한 문장은 제외하여, 학습할 가치가 있거나, 원어민들이 자주 쓰는 핵심 구문 위주로 '최대 20개'를 추출하십시오. 
            2. 단어: 기초 단어는 철저히 배제하십시오. TOEFL 100점 이상 수준의 고급 어휘, 숙어(Idiom), 전문 용어(Jargon)를 중심으로 '가능한 한 많이(제한 없음)' 추출하십시오.
            """

        prompt = f"""아래 데이터를 분석하여 핵심 단어와 문장을 추출해 주세요.
        [제외 단어]: {exclude_list}
        [출력 규칙]: {prompt_rule}
        [출력 포맷]: {{"sentences": [], "vocab": []}}
        [데이터]: {text[:25000]}"""

        try:
            response = self.client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=self.sys_instruct,
                    response_mime_type="application/json",
                    temperature=0.3
                )
            )
            return json.loads(response.text)
        except Exception as e:
            print(f"❌ AI 분석 실패: {e}")
            return None

class ContentFetcher:
    @staticmethod
    def fetch_youtube(v_id):
        print(f"🎬 유튜브 자막 가져오는 중: {v_id}")
        try:
            transcript_list = YouTubeTranscriptApi().list(v_id)
            try:
                transcript = transcript_list.find_manually_created_transcript(['en', 'en-US'])
            except:
                transcript = transcript_list.find_generated_transcript(['en'])
            return TextFormatter().format_transcript(transcript.fetch())
        except Exception as e:
            print(f"❌ 유튜브 자막 오류: {e}")
            return None

    @staticmethod
    def fetch_website(url):
        print(f"🌐 웹사이트 추출 중: {url}")
        try:
            res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
            soup = BeautifulSoup(res.text, 'html.parser')
            for s in soup(['script', 'style', 'nav', 'footer']): s.decompose()
            return "\\n".join([p.get_text() for p in soup.find_all('p')]) or soup.get_text()
        except Exception as e:
            print(f"❌ 웹사이트 오류: {e}")
            return None

def main():
    print("=== Anki Link Extractor ===")
    user_input = input("링크(YouTube/Website)를 입력하세요: ").strip()
    
    analyzer = GeminiAnalyzer()
    existing_vocab = AnkiManager.get_existing_vocab()
    content = None

    if 'youtube.com' in user_input or 'youtu.be' in user_input:
        v_id = re.search(r"(?:v=|\/)([0-9A-Za-z_-]{11})", user_input)
        if v_id: content = ContentFetcher.fetch_youtube(v_id.group(1))
    elif user_input:
        content = ContentFetcher.fetch_website(user_input)

    if content:
        result = analyzer.analyze(content, existing_vocab)
        if result:
            AnkiManager.add_notes(result)
    else:
        print("❌ 데이터를 가져오지 못했습니다.")

if __name__ == "__main__":
    main()
