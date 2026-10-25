"""
Migrate 7 word-like Chinese Sentence notes to Chinese Vocabulary notes.
"""

import json
import os
import re
import sys
from pathlib import Path

os.environ["no_proxy"] = "*"
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from google import genai
from google.genai import types
from integrations.anki_connect import AnkiConnector
from config import GOOGLE_API_KEY

TARGET_NIDS = [
    1708420543350,  # 一百
    1708420562895,  # 一千
    1708420580927,  # 一万
    1708420638270,  # 两天
    1708420660942,  # 一个星期
    1708420688081,  # 十天
    1708420716410   # 护照
]

def generate_vocab_details(words_info):
    """Generate POS and 2 HSK 1-3 example sentences for each word using Gemini."""
    client = genai.Client(api_key=GOOGLE_API_KEY)
    
    prompt = """당신은 초급 중국어 교육 전문가입니다. 아래 7개 단어 각각에 대해 품사(한국어)와 HSK 1~3(A1~A2) 수준의 아주 쉬운 예문 2개를 생성해 주세요.
각 예문은 반드시 간체자 한자 문장, 성조가 표기된 병음, 자연스러운 한국어 번역을 포함해야 합니다.

출력 JSON 형식:
[
  {
    "word": "一百",
    "pos": "수사",
    "examples": [
      "这件衣服一百块。 (zhè jiàn yīfu yībǎi kuài. / 이 옷은 100위안입니다.)",
      "学校有一百个学生。 (xuéxiào yǒu yībǎi gè xuésheng. / 학교에 학생이 100명 있습니다.)"
    ]
  },
  ...
]

단어 목록:
"""
    for item in words_info:
        prompt += f"- 단어: {item['word']} / 뜻: {item['meaning']} / 병음: {item['pinyin']}\n"

    response = client.models.generate_content(
        model="gemini-2.5-flash-lite",
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.2
        )
    )
    return json.loads(response.text)

def run():
    print("[*] Fetching existing 7 sentence notes...")
    notes = AnkiConnector.invoke("notesInfo", notes=TARGET_NIDS)
    
    words_info = []
    for n in notes:
        f = n["fields"]
        words_info.append({
            "nid": n["noteId"],
            "word": f.get("문장", {}).get("value", "").strip(),
            "meaning": f.get("뜻", {}).get("value", "").strip(),
            "pinyin": f.get("한어병음", {}).get("value", "").strip(),
            "audio": f.get("소리", {}).get("value", "").strip()
        })
        
    print(f"[*] Generating POS & examples for {len(words_info)} words with Gemini...")
    generated_data = generate_vocab_details(words_info)
    gen_map = {item["word"]: item for item in generated_data}
    
    new_notes = []
    for w in words_info:
        word_text = w["word"]
        gen = gen_map.get(word_text, {})
        pos = gen.get("pos", "명사")
        examples = " ||| ".join(gen.get("examples", []))
        
        new_note = {
            "deckName": "1. Language::1.3. Chinese::Vocabulary",
            "modelName": "Chinese Vocabulary",
            "fields": {
                "단어": word_text,
                "뜻": w["meaning"],
                "한어병음": w["pinyin"],
                "소리": w["audio"],
                "품사": pos,
                "예문": examples,
                "사진": ""
            },
            "options": {
                "allowDuplicate": False,
                "duplicateScope": "deck"
            }
        }
        new_notes.append(new_note)

    print(f"[*] Adding {len(new_notes)} notes to Chinese Vocabulary...")
    added_ids = AnkiConnector.invoke("addNotes", notes=new_notes)
    print(f"  Added note IDs: {added_ids}")

    print(f"[*] Deleting old 7 sentence notes...")
    AnkiConnector.invoke("deleteNotes", notes=TARGET_NIDS)
    print("  Old sentence notes deleted.")

    # Clean up wrongly linked non-sentence items from existing vocab cards
    print("[*] Cleaning up stray short word matches in vocab examples...")
    stray_patterns = [
        r"\|\|\|\s*一百\s*\([^)]*\)",
        r"\|\|\|\s*一千\s*\([^)]*\)",
        r"\|\|\|\s*十天\s*\([^)]*\)",
        r"\|\|\|\s*一个星期\s*\([^)]*\)",
    ]
    all_vocab_ids = AnkiConnector.invoke("findNotes", query="\"note:Chinese Vocabulary\"")
    vocab_notes = AnkiConnector.invoke("notesInfo", notes=all_vocab_ids)
    
    cleaned_count = 0
    for vn in vocab_notes:
        vid = vn["noteId"]
        ex = vn["fields"].get("예문", {}).get("value", "")
        original_ex = ex
        for pat in stray_patterns:
            ex = re.sub(pat, "", ex).strip()
        # Clean double separators
        ex = re.sub(r"\s*\|\|\|\s*\|\|\|\s*", " ||| ", ex)
        ex = ex.strip(" |")
        if ex != original_ex:
            AnkiConnector.invoke("updateNoteFields", note={
                "id": vid,
                "fields": {"예문": ex}
            })
            cleaned_count += 1
            print(f"  Cleaned vocab note {vid}: {vn['fields'].get('단어', {}).get('value')}")

    print(f"✅ Migration finished! Added: {len([x for x in added_ids if x])}, Deleted: 7, Cleaned vocab notes: {cleaned_count}")

if __name__ == "__main__":
    run()
