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
    {"word": "association", "note_id": 1611626225610, "chunk": "in association with A", "pos": "prep", "meaning": "A와 협력하여, 제휴하여"},
    {"word": "miscellaneous", "note_id": 1662366508041, "chunk": "miscellaneous expenses", "pos": "n", "meaning": "잡비, 기타 경비"},
    {"word": "occasionally", "note_id": 1661488456555, "chunk": "only occasionally", "pos": "adv", "meaning": "아주 가끔, 드물게"},
    {"word": "informal", "note_id": 1689158326162, "chunk": "informal gathering", "pos": "n", "meaning": "격식 없는 모임, 편안한 자리"},
    {"word": "bizarre", "note_id": 1746876206079, "chunk": "bizarre behavior", "pos": "n", "meaning": "기이한 행동, 괴상한 행동"},
    {"word": "enormous", "note_id": 1615113395413, "chunk": "an enormous amount of A", "pos": "n", "meaning": "막대한 양의 A, 엄청난 양의 A"},
    {"word": "contribute", "note_id": 1611575046006, "chunk": "contribute to A", "pos": "v", "meaning": "A에 기여하다, A의 원인이 되다"},
    {"word": "inspection", "note_id": 1654939544048, "chunk": "a close inspection", "pos": "n", "meaning": "정밀 검사, 면밀한 조사"},
    {"word": "liable", "note_id": 1662685005178, "chunk": "be liable for A", "pos": "adj", "meaning": "A에 대해 (법적/재정적) 책임이 있는"},
    {"word": "consult", "note_id": 1659223769930, "chunk": "consult with A", "pos": "v", "meaning": "A(전문가 등)와 상의하다, 상담하다"},
    {"word": "handy", "note_id": 1662685005148, "chunk": "come in handy", "pos": "v", "meaning": "유용하게 쓰이다, 요긴하게 쓰이다"},
    {"word": "superb", "note_id": 1657719178805, "chunk": "a superb performance", "pos": "n", "meaning": "대단히 훌륭한 성과/공연"},
    {"word": "excessive", "note_id": 1658384848763, "chunk": "excessive use of A", "pos": "n", "meaning": "A의 과도한 사용, 남용"},
    {"word": "pledge", "note_id": 1756436164806, "chunk": "make a pledge to V", "pos": "v", "meaning": "~하겠다고 엄숙히 서약/약속하다"},
    {"word": "overall", "note_id": 1662366571503, "chunk": "overall performance", "pos": "n", "meaning": "전반적인 실적/성과"},
    {"word": "budget", "note_id": 1647902752194, "chunk": "on a tight budget", "pos": "adv", "meaning": "빠듯한 예산으로"},
    {"word": "instant", "note_id": 1609761309522, "chunk": "in an instant", "pos": "adv", "meaning": "순식간에, 눈 깜짝할 사이에"},
    {"word": "comfortable", "note_id": 1614139331065, "chunk": "feel comfortable with A", "pos": "v", "meaning": "A에 대해 편안함을 느끼다, 거리낌이 없다"},
    {"word": "lay", "note_id": 1609761309775, "chunk": "lay out A", "pos": "v", "meaning": "A(계획·이유)를 명확히 제시하다/설명하다"},
    {"word": "necessarily", "note_id": 1708861811013, "chunk": "not necessarily", "pos": "adv", "meaning": "반드시 ~인 것은 아니다, 꼭 그렇지는 않다"}
]

prompt = f"""
다음 20개 영어 청크 표현에 대해 각각 실전적인 원어민 예문 2개, 자연스러운 한국어 번역, 그리고 원어민 뉘앙스 해설을 작성해주세요.
- 예문은 일상 비즈니스, 학업, 실생활에서 원어민들이 자연스럽게 구사하는 고급스럽고 현실적인 문장으로 작성하세요.
- 구문(chunk)이 문장 안에서 명확하게 활용되도록 구성하세요.

[목록]:
{json.dumps(lineup, ensure_ascii=False, indent=2)}

반환 형식: 아래 스키마를 따르는 JSON 배열:
[
  {{
    "note_id": 12345,
    "original_word": "association",
    "chunk": "in association with A",
    "pos": "prep",
    "meaning": "A와 협력하여, 제휴하여",
    "example_1": "The exhibition was organized in association with the British Museum.",
    "trans_1": "그 전시회는 대영박물관과의 협력 하에 조직되었다.",
    "example_2": "We are developing this project in association with local partners.",
    "trans_2": "우리는 현지 파트너들과 제휴하여 이 프로젝트를 진행하고 있다.",
    "explanation": "단순한 협력을 넘어 공식적인 기관/파트너와의 제휴 관계를 나타낼 때 주로 전치사구로 사용됩니다."
  }}
]
"""

print("[*] Generating curated examples and nuances with Gemini 2.5 Flash...")
response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents=prompt,
    config=types.GenerateContentConfig(
        response_mime_type="application/json",
        temperature=0.2
    )
)

curated_items = json.loads(response.text)
with open("data/batch_2_promote_curated.json", "w", encoding="utf-8") as f:
    json.dump(curated_items, f, ensure_ascii=False, indent=2)

print(f"✓ Successfully generated curated examples for all {len(curated_items)} items and saved to data/batch_2_promote_curated.json!")
