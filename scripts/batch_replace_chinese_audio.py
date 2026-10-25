"""
Batch generate and replace Chinese card audio with GCP Chirp3-HD voices.
Selected voices: Charon (M), Achird (M), Achernar (F), Aoede (F).
"""

import base64
import os
import random
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from tqdm import tqdm

os.environ["no_proxy"] = "*"
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from google.cloud import texttospeech
from integrations.anki_connect import AnkiConnector
from config import VOICE_LIST_ZH

MODEL_ZH_VOCAB = "Chinese Vocabulary"
MODEL_ZH_SENT = "Chinese Sentence"

client = texttospeech.TextToSpeechClient()

def synthesize_audio_with_retry(text: str, is_vocab: bool = True, max_retries: int = 5) -> str:
    """Generate audio using selected Chinese Chirp3-HD voices at 1.0x speed."""
    voice_name = random.choice(VOICE_LIST_ZH)
    synthesis_input = texttospeech.SynthesisInput(text=text)
    voice = texttospeech.VoiceSelectionParams(
        language_code="cmn-CN",
        name=voice_name
    )
    # 단어, 문장 모두 기본 1.0 배속으로 통일
    speaking_rate = 1.0
    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.MP3,
        speaking_rate=speaking_rate
    )
    
    last_err = None
    for attempt in range(max_retries):
        try:
            res = client.synthesize_speech(input=synthesis_input, voice=voice, audio_config=audio_config)
            short_voice = voice_name.split("-")[-1]
            filename = f"anki_zh_chirp_{short_voice}_{uuid.uuid4().hex[:8]}.mp3"
            b64_data = base64.b64encode(res.audio_content).decode("utf-8")
            AnkiConnector.invoke("storeMediaFile", filename=filename, data=b64_data)
            return f"[sound:{filename}]"
        except Exception as e:
            last_err = e
            if "429" in str(e) or "Resource has been exhausted" in str(e):
                sleep_time = (2 ** attempt) + random.uniform(0.5, 1.5)
                time.sleep(sleep_time)
            else:
                time.sleep(1.0)
                
    raise last_err

def process_item(item):
    nid = item["nid"]
    text = item["text"]
    is_vocab = item["is_vocab"]
    try:
        sound_tag = synthesize_audio_with_retry(text, is_vocab=is_vocab)
        AnkiConnector.invoke("updateNoteFields", note={
            "id": nid,
            "fields": {"소리": sound_tag}
        })
        return True, nid, None
    except Exception as e:
        return False, nid, str(e)

def run():
    print("[*] Loading Chinese Vocabulary and Sentence notes...")
    vocab_nids = AnkiConnector.invoke("findNotes", query=f'\"note:{MODEL_ZH_VOCAB}\"')
    sent_nids = AnkiConnector.invoke("findNotes", query=f'\"note:{MODEL_ZH_SENT}\"')
    
    vocab_notes = AnkiConnector.invoke("notesInfo", notes=vocab_nids)
    sent_notes = AnkiConnector.invoke("notesInfo", notes=sent_nids)
    
    items_to_process = []
    
    for n in vocab_notes:
        nid = n["noteId"]
        word = n["fields"].get("단어", {}).get("value", "").strip()
        if word:
            items_to_process.append({
                "nid": nid,
                "text": word,
                "is_vocab": True
            })
            
    for n in sent_notes:
        nid = n["noteId"]
        sent = n["fields"].get("문장", {}).get("value", "").strip()
        if sent:
            items_to_process.append({
                "nid": nid,
                "text": sent,
                "is_vocab": False
            })
            
    total = len(items_to_process)
    print(f"[*] Total items to synthesize with Chirp3-HD (1.0x): {total}")
    if total == 0:
        print("✅ All 792 items already have Chirp3-HD audio! Nothing to do.")
        return

    success_count = 0
    fail_count = 0

    # Rate limiting: 4 workers to stay well within GCP TTS quota
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {executor.submit(process_item, item): item for item in items_to_process}
        for future in tqdm(as_completed(futures), total=total, desc="Synthesizing Chirp3-HD"):
            ok, nid, err = future.result()
            if ok:
                success_count += 1
            else:
                fail_count += 1
                print(f"  Failed note {nid}: {err}")

    print(f"\n✅ Chirp3-HD audio replacement complete! Success: {success_count}, Failed: {fail_count}")

if __name__ == "__main__":
    run()
