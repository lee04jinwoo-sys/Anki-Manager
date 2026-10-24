"""
Import Tier 1 Idioms into Anki:
- 37 Phrase-style idioms into 'English Vocabulary' (with 2 examples ||| separated, nuance explanation, TTS, freq::tier1_essential tag)
- 13 Sentence-style expressions into 'English Sentence' (with context translation, TTS, freq::tier1_essential tag)
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
from config import DECK_VOCAB, MODEL_VOCAB, DECK_SENTENCE, MODEL_SENTENCE
from integrations.anki_connect import AnkiConnector
from integrations.audio import AnkiTTSFiller
from core.link_manager import LinkManager

DB_PATH = BASE_DIR / "data" / "idioms_pool.db"

SENTENCE_PHRASES = {
    'not at all', 'about time', 'what are you up to', 'business is business',
    'what you see is what you get', 'what are you like?', "what's not to like",
    'get off my back!', 'over and out', "you're on", 'get used to it',
    'all the best', 'no news is good news'
}


def fetch_candidates():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "SELECT id, rank, clean_phrase, meaning_ko, definition_en, example_en "
        "FROM idioms WHERE meaning_ko IS NOT NULL ORDER BY rank ASC, clean_phrase ASC"
    )
    rows = c.fetchall()
    conn.close()

    vocabs = []
    sentences = []
    for r in rows:
        item = {
            "id": r[0],
            "rank": r[1],
            "phrase": r[2],
            "meaning_ko": r[3],
            "definition_en": r[4],
            "example_en": r[5]
        }
        if r[2] in SENTENCE_PHRASES:
            sentences.append(item)
        else:
            vocabs.append(item)
    return vocabs, sentences


def enrich_vocab_batch(client: genai.Client, batch):
    items_text = "\n".join([
        f"- {i+1}. phrase: '{item['phrase']}', meaning: '{item['meaning_ko']}', definition: '{item['definition_en']}'"
        for i, item in enumerate(batch)
    ])

    prompt = f"""당신은 Anki 영어 어휘 카드를 제작하는 영어 교육 전문가입니다.
다음 관용구 목록에 대해 각각:
1. 원어민이 일상에서 자연스럽게 쓰는 실생활 예문 2개 (example_1, example_2)를 작성하세요.
   - 중요 규칙: 예문 안에 해당 관용구(phrase)가 반드시 원형 또는 자연스러운 시제/인칭 변화 형태로 포함되어야 합니다.
   - 너무 길지 않고(1~2문장), 상황이 생생하게 연상되는 문장이어야 합니다.
2. 한국어 뉘앙스 및 상황 설명 (explanation)을 2~3문장으로 간결하고 명확하게 작성하세요.
   - 언제 쓰는지, 어떤 감정이나 뉘앙스를 담고 있는지 설명하세요.

대상 관용구:
{items_text}

반드시 아래 JSON 배열 형식으로만 응답하세요:
[
  {{
    "phrase": "관용구",
    "example_1": "예문 1",
    "example_2": "예문 2",
    "explanation": "뉘앙스 설명"
  }}
]
"""
    resp = client.models.generate_content(
        model="gemini-2.5-flash-lite",
        contents=prompt,
        config={"response_mime_type": "application/json"}
    )
    return json.loads(resp.text)


def enrich_sentence_batch(client: genai.Client, sentences):
    items_text = "\n".join([
        f"- {i+1}. phrase: '{item['phrase']}', meaning: '{item['meaning_ko']}', definition: '{item['definition_en']}'"
        for i, item in enumerate(sentences)
    ])

    prompt = f"""당신은 영어 회화 전문가입니다.
다음은 독립적인 문장/발화로 쓰이는 영어 표현들입니다.
각각에 대해:
1. 문장 부호(마침표, 물음표, 느낌표)와 대문자가 완벽하게 적용된 완성형 영어 문장(sentence)
2. 상황과 어조를 살린 가장 자연스러운 한국어 구어체 해설(meaning_ko)

대상 표현:
{items_text}

반드시 아래 JSON 배열 형식으로만 응답하세요:
[
  {{
    "phrase": "원래 표현",
    "sentence": "완성형 영어 문장",
    "meaning_ko": "자연스러운 한국어 구어체 해설"
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
    print("=== Tier 1 관용구 Anki 등록 파이프라인 시작 ===")
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("GOOGLE_API_KEY missing in .env")
    client = genai.Client(api_key=api_key)

    vocabs, sentences = fetch_candidates()
    print(f"후보 로드 완료: 단어 카드 {len(vocabs)}개, 문장 카드 {len(sentences)}개")

    # 1. 단어 카드 보강 (Gemini)
    print("\n[1/4] 단어 카드 37개 예문 및 해설 생성 중...")
    vocab_enriched_map = {}
    # Split into 2 chunks for safety (20 + 17)
    chunks = [vocabs[:20], vocabs[20:]]
    for chunk_idx, chunk in enumerate(chunks, 1):
        print(f"  Chunk {chunk_idx}/{len(chunks)} ({len(chunk)}개) 호출 중...")
        enriched = enrich_vocab_batch(client, chunk)
        for item in enriched:
            vocab_enriched_map[item["phrase"].lower().strip()] = item
        time.sleep(1)

    # 2. 문장 카드 보강 (Gemini)
    print("\n[2/4] 문장 카드 13개 포맷팅 및 해설 생성 중...")
    sent_enriched_map = {}
    sent_enriched = enrich_sentence_batch(client, sentences)
    for item in sent_enriched:
        sent_enriched_map[item["phrase"].lower().strip()] = item

    # 3. Anki 등록 (단어 카드 37개)
    print("\n[3/4] Anki 단어 카드(English Vocabulary) 등록 중...")
    vocab_success = 0
    vocab_skipped = 0
    imported_ids = []

    for item in vocabs:
        norm = item["phrase"].lower().strip()
        enr = vocab_enriched_map.get(norm, {})

        ex1 = enr.get("example_1", item["example_en"] or "").strip()
        ex2 = enr.get("example_2", "").strip()
        if ex1 and ex2:
            combined_examples = f"{ex1} ||| {ex2}"
        else:
            combined_examples = ex1 or ex2

        explanation = enr.get("explanation", item["definition_en"] or "").strip()

        # Check existing note
        existing = AnkiConnector.invoke("findNotes", query=f'note:"{MODEL_VOCAB}" "단어:{item["phrase"]}"')
        if existing:
            print(f"  [건너뜀] 이미 존재함: {item['phrase']} (Note ID: {existing[0]})")
            vocab_skipped += 1
            imported_ids.append(item["id"])
            continue

        # TTS Audio
        sound_tag, _ = AnkiTTSFiller.generate_gtts(item["phrase"])

        fields = {
            "단어": item["phrase"],
            "뜻": item["meaning_ko"],
            "품사": "idiom",
            "유의어": "",
            "예문": combined_examples,
            "사진": "",
            "설명": explanation,
            "소리": sound_tag
        }

        try:
            nid = AnkiConnector.invoke("addNote", note={
                "deckName": DECK_VOCAB,
                "modelName": MODEL_VOCAB,
                "fields": fields,
                "tags": ["freq::tier1_essential"],
                "options": {"allowDuplicate": False}
            })
            if nid:
                vocab_success += 1
                imported_ids.append(item["id"])
                try:
                    LinkManager.index_single_vocab(nid, item["phrase"], item["meaning_ko"], "idiom")
                except Exception as le:
                    print(f"    Link indexing warning: {le}")
                print(f"  [등록 성공] {item['phrase']} -> Note {nid}")
        except Exception as e:
            print(f"  [등록 실패] {item['phrase']}: {e}")

    # 4. Anki 등록 (문장 카드 13개)
    print("\n[4/4] Anki 문장 카드(English Sentence) 등록 중...")
    sent_success = 0
    sent_skipped = 0

    for item in sentences:
        norm = item["phrase"].lower().strip()
        enr = sent_enriched_map.get(norm, {})

        sentence_text = enr.get("sentence", item["phrase"]).strip()
        meaning = enr.get("meaning_ko", item["meaning_ko"]).strip()

        # Check existing note
        existing = AnkiConnector.invoke("findNotes", query=f'note:"{MODEL_SENTENCE}" "문장:{sentence_text}"')
        if existing:
            print(f"  [건너뜀] 이미 존재함: {sentence_text} (Note ID: {existing[0]})")
            sent_skipped += 1
            imported_ids.append(item["id"])
            continue

        # TTS Audio
        sound_tag, _ = AnkiTTSFiller.generate_gtts(sentence_text)

        fields = {
            "문장": sentence_text,
            "해설": meaning,
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
                sent_success += 1
                imported_ids.append(item["id"])
                print(f"  [등록 성공] {sentence_text} -> Note {nid}")
        except Exception as e:
            print(f"  [등록 실패] {sentence_text}: {e}")

    # 5. DB 상태 갱신
    if imported_ids:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.executemany("UPDATE idioms SET status='imported' WHERE id = ?", [(i,) for i in imported_ids])
        conn.commit()
        conn.close()
        print(f"\nDB 상태 갱신 완료: {len(imported_ids)}건 'imported' 처리")

    # 6. Anki 동기화
    try:
        print("\nAnkiWeb 동기화 요청 중...")
        AnkiConnector.invoke("sync")
        print("AnkiWeb 동기화 트리거 완료!")
    except Exception as se:
        print(f"AnkiWeb 동기화 실패 (수동 동기화 필요): {se}")

    print(f"\n=== 등록 결과 요약 ===")
    print(f"단어 카드(English Vocabulary): 성공 {vocab_success}건, 건너뜀 {vocab_skipped}건")
    print(f"문장 카드(English Sentence):   성공 {sent_success}건, 건너뜀 {sent_skipped}건")
    print(f"총 등록된 표현: {vocab_success + sent_success}건")


if __name__ == "__main__":
    main()
