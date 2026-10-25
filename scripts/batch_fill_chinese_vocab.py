"""
Batch generator for missing Chinese Vocabulary fields (품사, 예문)
Enforces strict HSK 1~3 (A1~A2) constraints.
"""

import json
import os
import sys
import time
from pathlib import Path
from google import genai
from google.genai import types
from dotenv import load_dotenv
from tqdm import tqdm

os.environ["no_proxy"] = "*"
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

load_dotenv(BASE_DIR / ".env")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

from config import (
    MODEL_ZH_VOCAB, NOTE_COMPLETOR_ZH_SYS_INSTRUCT,
    NOTE_COMPLETOR_MODEL, GEMINI_DEFAULT_TEMPERATURE
)
from integrations.anki_connect import AnkiConnector

BATCH_SIZE = 10

def generate_batch(client, items):
    prompt = (
        "다음 중국어 기초 단어 목록에 대해 '품사'와 '예문'을 JSON 배열 형태로 생성하세요.\n"
        "각 항목에 대해 입력된 id를 그대로 유지해야 합니다.\n"
        "[입력 단어 목록]\n" + json.dumps(items, ensure_ascii=False, indent=2) + "\n\n"
        "[출력 스키마 형식 (JSON 배열)]:\n"
        "[\n"
        "  {\n"
        "    \"id\": 12345,\n"
        "    \"품사\": \"대명사\",\n"
        "    \"예문\": \"중국어_간체자_문장1 (성조병음 / 한국어해석) ||| 중국어_간체자_문장2 (성조병음 / 한국어해석)\"\n"
        "  }\n"
        "]\n\n"
        "[엄격 제약사항]\n"
        "1. 예문은 철저히 HSK 1~3급(A1~A2) 초급 기초 단어로만 구성할 것. 6~14자 단문.\n"
        "2. 반드시 간체자 표기, 괄호 안에 성조 부호 포함 병음과 한국어 해석 필수 표기.\n"
        "3. 단어당 예문 2개를 ' ||| '로 연결할 것."
    )

    response = client.models.generate_content(
        model=NOTE_COMPLETOR_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=NOTE_COMPLETOR_ZH_SYS_INSTRUCT,
            response_mime_type="application/json",
            temperature=GEMINI_DEFAULT_TEMPERATURE
        )
    )
    
    text = response.text.strip()
    return json.loads(text, strict=False)

def run_batch_fill(limit=None):
    client = genai.Client(api_key=GOOGLE_API_KEY)
    
    print(f"[*] Fetching notes for {MODEL_ZH_VOCAB}...")
    nids = AnkiConnector.invoke("findNotes", query=f"\"note:{MODEL_ZH_VOCAB}\"")
    print(f"  Total notes found: {len(nids)}")
    
    notes_info = AnkiConnector.invoke("notesInfo", notes=nids)
    
    # Filter notes that have empty 예문
    targets = []
    for n in notes_info:
        nid = n["noteId"]
        flds = n["fields"]
        word = flds.get("단어", {}).get("value", "").strip()
        meaning = flds.get("뜻", {}).get("value", "").strip()
        pinyin = flds.get("한어병음", {}).get("value", "").strip()
        ex = flds.get("예문", {}).get("value", "").strip()
        
        if word and not ex:
            targets.append({
                "id": nid,
                "단어": word,
                "한어병음": pinyin,
                "뜻": meaning
            })
            
    print(f"  Notes needing examples: {len(targets)}")
    if limit:
        targets = targets[:limit]
        print(f"  (Limited to first {limit} notes for testing)")
        
    if not targets:
        print("✨ No notes need updating.")
        return

    # Process in batches
    success_count = 0
    pbar = tqdm(total=len(targets), desc="Filling Chinese Vocab")
    
    for i in range(0, len(targets), BATCH_SIZE):
        batch = targets[i:i + BATCH_SIZE]
        try:
            results = generate_batch(client, batch)
            if isinstance(results, dict):
                results = [results]
                
            for res in results:
                nid = res.get("id")
                pos = res.get("품사", "").strip()
                ex = res.get("예문", "").strip()
                
                if nid and ex:
                    update_dict = {"예문": ex}
                    if pos:
                        update_dict["품사"] = pos
                    AnkiConnector.invoke("updateNoteFields", note={"id": nid, "fields": update_dict})
                    success_count += 1
            pbar.update(len(batch))
        except Exception as e:
            print(f"\n[!] Error processing batch {i // BATCH_SIZE}: {e}")
            time.sleep(2)
            
    pbar.close()
    print(f"\n✅ Finished! Successfully updated {success_count} notes.")

if __name__ == "__main__":
    limit_arg = int(sys.argv[1]) if len(sys.argv) > 1 else None
    run_batch_fill(limit=limit_arg)
