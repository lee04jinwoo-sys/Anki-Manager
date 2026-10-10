import os
import json
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()
api_key = os.environ.get("GOOGLE_API_KEY")
if not api_key:
    raise ValueError("GOOGLE_API_KEY is not set.")

client = genai.Client(api_key=api_key)

lineup = [
    {"word": "occur", "note_id": 1614666409524, "chunk": "occur to A", "pos": "v", "meaning": "A에게 (생각 등이) 문득 떠오르다"},
    {"word": "grant", "note_id": 1609761309947, "chunk": "take A for granted", "pos": "v", "meaning": "A를 당연하게 여기다"},
    {"word": "council", "note_id": 1741936364157, "chunk": "city council", "pos": "n", "meaning": "시의회"},
    {"word": "counsel", "note_id": 1628251149287, "chunk": "legal counsel", "pos": "n", "meaning": "법률 자문, 변호인"},
    {"word": "prospect", "note_id": 1661763236207, "chunk": "the prospect of A", "pos": "n", "meaning": "A할 가능성, 전망"},
    {"word": "separate", "note_id": 1613815306879, "chunk": "separate A from B", "pos": "v", "meaning": "A를 B로부터 분리하다/구분하다"},
    {"word": "strain", "note_id": 1729751838733, "chunk": "put a strain on A", "pos": "v", "meaning": "A에 심한 부담/압박을 주다"},
    {"word": "committed", "note_id": 1708949928829, "chunk": "be committed to A", "pos": "adj", "meaning": "A에 전념하다, 헌신하다"},
    {"word": "courtesy", "note_id": 1709091121747, "chunk": "by courtesy of A", "pos": "adv", "meaning": "A의 호의로, 협찬으로, 덕분에"},
    {"word": "compliant", "note_id": 1781852320105, "chunk": "compliant with A", "pos": "adj", "meaning": "A를 준수하는, 부합하는"},
    {"word": "robust", "note_id": 1753598458619, "chunk": "robust health", "pos": "n", "meaning": "왕성한/튼튼한 건강"},
    {"word": "delight", "note_id": 1622812795074, "chunk": "to A's delight", "pos": "adv", "meaning": "A가 아주 기쁘게도"},
    {"word": "criterion", "note_id": 1614857679981, "chunk": "criterion for A", "pos": "n", "meaning": "A에 대한 기준, 평가 규준"},
    {"word": "tenant", "note_id": 1660860829550, "chunk": "landlord and tenant", "pos": "n", "meaning": "집주인과 세입자"},
    {"word": "temporal", "note_id": 1648648348007, "chunk": "temporal lobe", "pos": "n", "meaning": "측두엽"},
    {"word": "engaging", "note_id": 1651749963001, "chunk": "engaging personality", "pos": "n", "meaning": "매력적인/호감을 주는 성격"},
    {"word": "affiliation", "note_id": 1654941417588, "chunk": "affiliation with A", "pos": "n", "meaning": "A와의 제휴, 소속, 관계"},
    {"word": "appliance", "note_id": 1753598458587, "chunk": "household appliance", "pos": "n", "meaning": "가전제품 (가정용 기기)"},
    {"word": "rear", "note_id": 1658373338380, "chunk": "at the rear of A", "pos": "adv", "meaning": "A의 뒤쪽에, 후방에"},
    {"word": "custom", "note_id": 1660390047469, "chunk": "go through customs", "pos": "v", "meaning": "세관을 통과하다"}
]

prompt = f"""
다음 20개 영어 청크 표현에 대해 각각 실전적인 원어민 예문 2개, 자연스러운 한국어 번역, 그리고 원어민 뉘앙스 해설을 작성해주세요.
[목록]:
{json.dumps(lineup, ensure_ascii=False, indent=2)}

반환 형식: 아래 스키마를 따르는 JSON 배열:
[
  {{
    "note_id": 12345,
    "original_word": "occur",
    "chunk": "occur to A",
    "pos": "v",
    "meaning": "A에게 (생각 등이) 문득 떠오르다",
    "example_1": "예문 1",
    "trans_1": "한글 번역 1",
    "example_2": "예문 2",
    "trans_2": "한글 번역 2",
    "explanation": "원어민 뉘앙스 해설"
  }}
]
"""

response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents=prompt,
    config=types.GenerateContentConfig(
        response_mime_type="application/json",
        temperature=0.2
    )
)

curated_items = json.loads(response.text)
with open("data/batch_20_promote_curated.json", "w", encoding="utf-8") as f:
    json.dump(curated_items, f, ensure_ascii=False, indent=2)

print(f"Successfully generated curated examples for all {len(curated_items)} items and saved to data/batch_20_promote_curated.json!")
