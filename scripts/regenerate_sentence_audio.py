"""Replace gTTS audio on English Sentence notes with Chirp3-HD audio (same voices/settings as AnkiTTSFiller).

Why: on 2026-10-11 the server Anki Manager had no Google Cloud credentials and silently fell back
to gTTS for sentence cards. This regenerates their audio on a machine that can reach Chirp
(the Mac) and writes it to the target Anki over AnkiConnect.

Writes only: storeMediaFile (new file) and updateNoteFields for the 소리 field.
Old gTTS files are not deleted; review history is not touched.
Every change is logged (note id, old and new 소리) to data/backups/tts-regen-*.jsonl first.

    # list targets, synthesize one sample, write nothing
    .venv/bin/python scripts/regenerate_sentence_audio.py --anki http://127.0.0.1:18765
    # write (optionally --limit 1 first)
    .venv/bin/python scripts/regenerate_sentence_audio.py --anki http://127.0.0.1:18765 --yes [--limit N]
    # undo from a log
    .venv/bin/python scripts/regenerate_sentence_audio.py --anki http://127.0.0.1:18765 --restore data/backups/tts-regen-....jsonl --yes
"""
import argparse
import base64
import json
import random
import re
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path

import requests
from google.cloud import texttospeech

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config import VOICE_LIST  # noqa: E402
from integrations.audio import clean_html  # noqa: E402

QUERY = 'note:"English Sentence" 소리:*anki_gtts_*'
SOUND_ONLY = re.compile(r"^\s*\[sound:anki_gtts_[0-9a-f]+\.mp3\]\s*$")


class Anki:
    def __init__(self, url):
        self.url = url
        self.s = requests.Session()
        self.s.trust_env = False

    def __call__(self, action, **params):
        # Every action used here gives the same result when repeated, so a dropped connection is retried.
        for attempt in range(3):
            try:
                r = self.s.post(self.url, json={"action": action, "version": 6, "params": params}, timeout=60,
                                headers={"Connection": "close"}).json()
                break
            except requests.exceptions.ConnectionError:
                if attempt == 2:
                    raise
                time.sleep(2)
        if r.get("error"):
            raise RuntimeError(f"{action}: {r['error']}")
        return r["result"]

    def notes_info(self, ids, chunk=40):
        out = []
        for i in range(0, len(ids), chunk):
            out += self("notesInfo", notes=ids[i:i + chunk])
        return out


def synthesize(client, text):
    voice_name = random.choice(VOICE_LIST)
    lang = "-".join(voice_name.split("-")[:2])
    resp = client.synthesize_speech(
        input=texttospeech.SynthesisInput(text=clean_html(text)),
        voice=texttospeech.VoiceSelectionParams(language_code=lang, name=voice_name),
        audio_config=texttospeech.AudioConfig(audio_encoding=texttospeech.AudioEncoding.MP3, speaking_rate=1.1),
    )
    return f"anki_gcp_{voice_name}_{uuid.uuid4().hex[:8]}.mp3", resp.audio_content


def restore(anki, log_path, yes):
    rows = [json.loads(line) for line in Path(log_path).read_text().splitlines() if line.strip()]
    print(f"{len(rows)} notes in {log_path}")
    if not yes:
        print("dry run: add --yes to restore")
        return
    for r in rows:
        anki("updateNoteFields", note={"id": r["note_id"], "fields": {"소리": r["old"]}})
    print("restored")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--anki", required=True)
    ap.add_argument("--yes", action="store_true", help="actually write")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--restore")
    args = ap.parse_args()
    anki = Anki(args.anki)

    if args.restore:
        return restore(anki, args.restore, args.yes)

    ids = sorted(anki("findNotes", query=QUERY))
    notes = anki.notes_info(ids)
    targets, skipped = [], []
    for n in notes:
        sound = n["fields"]["소리"]["value"]
        sentence = n["fields"]["문장"]["value"]
        (targets if SOUND_ONLY.match(sound) and clean_html(sentence) else skipped).append(n)
    if args.limit:
        targets = targets[: args.limit]
    print(f"found {len(notes)} notes; {len(targets)} to regenerate; {len(skipped)} skipped (소리 has more than one gTTS tag or 문장 is empty)")
    for n in skipped:
        print("   skip", n["noteId"], n["fields"]["소리"]["value"][:80])

    client = texttospeech.TextToSpeechClient()
    if not args.yes:
        sample = targets[0]
        name, audio = synthesize(client, sample["fields"]["문장"]["value"])
        print(f"dry run: Chirp works ({len(audio)} bytes for note {sample['noteId']}, voice file {name}); nothing written")
        print("add --yes to write")
        return

    log_path = ROOT / "data" / "backups" / f"tts-regen-{datetime.now():%Y%m%d-%H%M%S}.jsonl"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    done = 0
    with open(log_path, "a", encoding="utf-8") as log:
        for n in targets:
            old = n["fields"]["소리"]["value"]
            name, audio = synthesize(client, n["fields"]["문장"]["value"])
            # AnkiConnect may store under a different name (the server lowercases); use what it returns.
            stored = anki("storeMediaFile", filename=name, data=base64.b64encode(audio).decode())
            if not anki("retrieveMediaFile", filename=stored):
                raise RuntimeError(f"stored media {stored!r} cannot be read back; stopping before changing note {n['noteId']}")
            new = f"[sound:{stored}]"
            log.write(json.dumps({"note_id": n["noteId"], "old": old, "new": new}, ensure_ascii=False) + "\n")
            log.flush()
            anki("updateNoteFields", note={"id": n["noteId"], "fields": {"소리": new}})
            done += 1
            if done % 20 == 0:
                print(f"   {done}/{len(targets)}")
    print(f"updated {done} notes; log: {log_path}")


if __name__ == "__main__":
    main()
