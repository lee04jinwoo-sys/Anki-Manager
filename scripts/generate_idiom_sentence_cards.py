"""
Generate 2 English Sentence cards for each of the 50 Tier 1 idioms:
- 37 phrase idioms get 2 sentence cards each (74 cards)
- 13 utterance expressions already have 1 sentence card, so they get 1 additional card each (13 cards)
Total new sentence cards: 87 (ensuring every one of the 50 idioms has exactly 2 sentence cards in 'English Sentence')
"""

import os
import sys
import json
import time
import sqlite3
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
load_dotenv(BASE_DIR / ".env")

from google import genai
from config import DECK_SENTENCE, MODEL_SENTENCE
from integrations.anki_connect import AnkiConnector
from integrations.audio import AnkiTTSFiller
from core.link_manager import LinkManager

DB_PATH = BASE_DIR / "data" / "idioms_pool.db"

# 13 expressions that already have 1 sentence card from the previous step
EXISTING_1_CARD_PHRASES = {
    'not at all', 'about time', 'what are you up to', 'business is business',
    'what you see is what you get', 'what are you like?', "what's not to like",
    'get off my back!', 'over and out', "you're on", 'get used to it',
    'all the best', 'no news is good news'
}


def load_all_50_idioms():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "SELECT id, rank, clean_phrase, meaning_ko, definition_en "
        "FROM idioms WHERE meaning_ko IS NOT NULL ORDER BY rank ASC, clean_phrase ASC"
    )
    rows = c.fetchall()
    conn.close()
    return [
        {
            "id": r[0],
            "rank": r[1],
            "phrase": r[2],
            "meaning_ko": r[3],
            "definition_en": r[4],
            "needs_count": 1 if r[2] in EXISTING_1_CARD_PHRASES else 2
        }
        for r in rows
    ]


def generate_sentences_batch(client: genai.Client, batch):
    items_text = "\n".join([
        f"- phrase: '{item['phrase']}' (meaning: {item['meaning_ko']}) -> generate {item['needs_count']} sentence(s)"
        for item in batch
    ])

    prompt = f"""당신은 Anki 영어 문장 카드를 제작하는 영어 교육 전문가입니다.
다음 관용구 목록에 대해 지정된 개수(1개 또는 2개)만큼 실생활 회화 문장과 자연스러운 한국어 번역을 작성하세요.

규칙:
1. 문장 안에 해당 관용구(phrase)가 자연스럽게 포함되어야 합니다.
2. 실생활(대화, 일상, 직장 등)에서 원어민이 입에 붙여 쓰는 생생한 구어체 문장이어야 합니다.
3. 문장 부호(마침표, 물음표, 느낌표)와 대소문자를 정확히 지키세요.
4. 한국어 번역은 직역투가 아닌 상황과 뉘앙스가 살아있는 자연스러운 구어체로 작성하세요.

대상 목록:
{items_text}

반드시 아래 JSON 배열 형식으로만 응답하세요:
[
  {{
    "phrase": "관용구",
    "sentences": [
      {{
        "sentence": "자연스러운 영어 문장",
        "translation": "자연스러운 한국어 번역"
      }}
    ]
  }}
]
"""
    resp = client.models.generate_content(
        model="gemini-2.5-flash-lite",
        contents=prompt,
        config={"response_mime_type": "application/json"}
    )
    return json.loads(resp.text)


def main():
    print("=== 표현당 문장 카드 2개 생성 파이프라인 시작 ===")
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("GOOGLE_API_KEY missing in .env")
    client = genai.Client(api_key=api_key)

    idioms = load_all_50_idioms()
    print(f"50개 표현 로드 완료 (37개: 2문장씩, 13개: 추가 1문장씩 -> 총 87개 문장 카드 목표)")

    # 1. Gemini로 문장 및 번역 생성 (2개 청크로 분할)
    print("\n[1/3] Gemini API로 실전문장 및 한국어 해설 생성 중...")
    chunks = [idioms[:25], idioms[25:]]
    generated_map = {}

    for idx, chunk in enumerate(chunks, 1):
        print(f"  청크 {idx}/{len(chunks)} ({len(chunk)}개 표현) 생성 중...")
        result = generate_sentences_batch(client, chunk)
        for item in result:
            generated_map[item["phrase"].lower().strip()] = item.get("sentences", [])
        time.sleep(1)

    # 2. Anki 문장 카드 등록
    print("\n[2/3] Anki 문장 카드(English Sentence) 등록 중...")
    success_count = 0
    skip_count = 0

    for item in idioms:
        phrase = item["phrase"].lower().strip()
        s_list = generated_map.get(phrase, [])
        if not s_list:
            print(f"  [경고] 생성 결과 없음: {item['phrase']}")
            continue

        for s_obj in s_list[:item["needs_count"]]:
            sentence_text = s_obj.get("sentence", "").strip()
            translation = s_obj.get("translation", "").strip()
            if not sentence_text or not translation:
                continue

            # 중복 검사
            existing = AnkiConnector.invoke("findNotes", query=f'note:"{MODEL_SENTENCE}" "문장:{sentence_text}"')
            if existing:
                print(f"  [건너뜀] 이미 존재하는 문장: {sentence_text[:40]}...")
                skip_count += 1
                continue

            # TTS 오디오 생성
            sound_tag, _ = AnkiTTSFiller.generate_gtts(sentence_text)

            fields = {
                "문장": sentence_text,
                "해설": translation,
                "소리": sound_tag
            }

            try:
                nid = AnkiConnector.invoke("addNote", note={
                    "deckName": DECK_SENTENCE,
                    "modelName": MODEL_SENTENCE,
                    "fields": fields,
                    "tags": ["freq::tier1_essential"],
                    "options": {"allowDuplicate": False}
                })
                if nid:
                    success_count += 1
                    try:
                        LinkManager.index_single_sentence(nid, sentence_text)
                    except Exception as le:
                        print(f"    Link indexing warning: {le}")
                    print(f"  [문장 카드 등록 성공] {item['phrase']} -> {sentence_text[:50]}... (Note {nid})")
            except Exception as e:
                print(f"  [문장 카드 등록 실패] {sentence_text[:40]}...: {e}")

    print(f"\n[3/3] AnkiWeb 동기화 트리거 중...")
    try:
        AnkiConnector.invoke("sync")
        print("로컬 AnkiWeb 동기화 요청 완료!")
    except Exception as se:
        print(f"AnkiWeb 동기화 실패 (수동 동기화 필요): {se}")

    print(f"\n=== 최종 결과 ===")
    print(f"신규 문장 카드 등록 성공: {success_count}건, 건너뜀: {skip_count}건")


if __name__ == "__main__":
    main()
