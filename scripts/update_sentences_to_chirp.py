"""
Regenerate audio for the 100 recently imported Tier 1 English Sentence notes using Google Cloud TTS Chirp3-HD.
"""

import sys
import os
import time
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
load_dotenv(BASE_DIR / ".env")

from google.cloud import texttospeech
from integrations.anki_connect import AnkiConnector
from integrations.audio import AnkiTTSFiller


def main():
    print("=== Tier 1 문장 카드 Chirp3-HD 오디오 일괄 교체 시작 ===")
    
    # 1. 대상 문장 카드 중 아직 gTTS인 것만 검색
    query = 'note:"English Sentence" tag:freq::tier1_essential "소리:*anki_gtts_*"'
    note_ids = AnkiConnector.invoke("findNotes", query=query) or []
    print(f"대상 gTTS 문장 카드: {len(note_ids)}개")

    if not note_ids:
        print("대상 카드가 없습니다 (모두 교체 완료).")
        return

    notes_info = AnkiConnector.invoke("notesInfo", notes=note_ids) or []
    tts_client = texttospeech.TextToSpeechClient()

    updated = 0
    failed = 0

    for i, info in enumerate(notes_info, 1):
        nid = info["noteId"]
        fields = info.get("fields", {})
        sentence = fields.get("문장", {}).get("value", "").strip()

        if not sentence:
            print(f"[{i}/{len(notes_info)}] Note {nid}: 문장 필드 비어있음 (스킵)")
            continue

        sound_tag = ""
        voice = ""
        for attempt in range(4):
            try:
                sound_tag, voice = AnkiTTSFiller.generate_random_tts(tts_client, sentence)
                if sound_tag:
                    break
            except Exception as e:
                if "429" in str(e):
                    print(f"  [429 Quota] 5초 대기 후 재시도... (시도 {attempt+1}/4)")
                    time.sleep(5)
                else:
                    print(f"  [에러] {e}")
                    break

        if not sound_tag:
            print(f"[{i}/{len(notes_info)}] Note {nid}: 오디오 생성 실패")
            failed += 1
            continue

        try:
            AnkiConnector.invoke("updateNoteFields", note={
                "id": nid,
                "fields": {"소리": sound_tag}
            })
            updated += 1
            print(f"[{i}/{len(notes_info)}] Note {nid} ({voice}) -> {sentence[:45]}...")
        except Exception as e:
            print(f"[{i}/{len(notes_info)}] Note {nid} 업데이트 실패: {e}")
            failed += 1

        time.sleep(0.3)

    print(f"\n오디오 교체 완료: 성공 {updated}건, 실패 {failed}건")

    # AnkiWeb 동기화 트리거
    try:
        print("\n로컬 AnkiWeb 동기화 요청 중...")
        AnkiConnector.invoke("sync")
        print("로컬 AnkiWeb 동기화 요청 완료!")
    except Exception as e:
        print(f"로컬 동기화 실패: {e}")

    # 원격 서버 동기화 트리거 (포트 18765)
    try:
        import requests
        print("원격 서버(oracle-quant) 동기화 요청 중...")
        res = requests.post("http://127.0.0.1:18765", json={"action": "sync", "version": 6}, timeout=15).json()
        print(f"원격 서버 동기화 결과: {res}")
    except Exception as e:
        print(f"원격 서버 동기화 실패: {e}")


if __name__ == "__main__":
    main()
