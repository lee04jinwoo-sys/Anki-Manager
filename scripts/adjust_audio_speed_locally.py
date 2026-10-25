"""
Adjust existing Chinese Chirp3-HD audio speed to exactly 1.0x locally using ffmpeg.
Cost: $0 (No API calls).
"""

import os
import re
import subprocess
import sys
from pathlib import Path
from tqdm import tqdm

os.environ["no_proxy"] = "*"
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from integrations.anki_connect import AnkiConnector

MEDIA_DIR = Path.home() / "Library/Application Support/Anki2/사용자 1/collection.media"

def extract_sound_filename(sound_tag: str) -> str:
    m = re.search(r'\[sound:([^\]]+)\]', sound_tag)
    return m.group(1).strip() if m else ""

def adjust_speed_ffmpeg(file_path: Path, tempo_factor: float) -> bool:
    if not file_path.exists():
        return False
    tmp_path = file_path.with_suffix(".tmp.mp3")
    cmd = [
        "/opt/homebrew/bin/ffmpeg",
        "-loglevel", "error",
        "-y",
        "-i", str(file_path),
        "-filter:a", f"atempo={tempo_factor:.8f}",
        "-vn",
        str(tmp_path)
    ]
    try:
        subprocess.run(cmd, check=True)
        if tmp_path.exists() and tmp_path.stat().st_size > 0:
            tmp_path.replace(file_path)
            return True
        return False
    except Exception as e:
        if tmp_path.exists():
            tmp_path.unlink()
        print(f"  Error converting {file_path.name}: {e}")
        return False

def run():
    print("[*] Finding Chinese Vocabulary and Sentence cards...")
    vocab_nids = AnkiConnector.invoke("findNotes", query='"note:Chinese Vocabulary"')
    sent_nids = AnkiConnector.invoke("findNotes", query='"note:Chinese Sentence"')
    
    vocab_notes = AnkiConnector.invoke("notesInfo", notes=vocab_nids)
    sent_notes = AnkiConnector.invoke("notesInfo", notes=sent_nids)
    
    # 0.95 -> 1.0: multiply by 1.0 / 0.95 = 1.05263158
    vocab_tempo = 1.0 / 0.95
    # 1.05 -> 1.0: multiply by 1.0 / 1.05 = 0.95238095
    sent_tempo = 1.0 / 1.05
    
    tasks = []
    
    for n in vocab_notes:
        sound = n["fields"].get("소리", {}).get("value", "")
        fn = extract_sound_filename(sound)
        if fn and "chirp" in fn:
            fpath = MEDIA_DIR / fn
            if fpath.exists():
                tasks.append((fpath, vocab_tempo, "vocab"))
                
    for n in sent_notes:
        sound = n["fields"].get("소리", {}).get("value", "")
        fn = extract_sound_filename(sound)
        if fn and "chirp" in fn:
            fpath = MEDIA_DIR / fn
            if fpath.exists():
                tasks.append((fpath, sent_tempo, "sentence"))

    print(f"[*] Total Chirp3-HD audio files to convert: {len(tasks)}")
    print(f"  - Vocab files (0.95x -> 1.0x): tempo factor {vocab_tempo:.4f}")
    print(f"  - Sentence files (1.05x -> 1.0x): tempo factor {sent_tempo:.4f}")

    success_cnt = 0
    fail_cnt = 0

    for fpath, factor, kind in tqdm(tasks, desc="Adjusting audio speed to 1.0x"):
        if adjust_speed_ffmpeg(fpath, factor):
            success_cnt += 1
        else:
            fail_cnt += 1

    print(f"\n✅ Local 1.0x speed adjustment complete! Success: {success_cnt}, Failed: {fail_cnt} (Cost: $0.00)")

if __name__ == "__main__":
    run()
