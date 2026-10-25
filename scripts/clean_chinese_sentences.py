"""
Clean HTML artifacts and awkward spaces from Chinese Sentence notes.
"""

import html
import os
import re
import sys
from pathlib import Path

os.environ["no_proxy"] = "*"
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from integrations.anki_connect import AnkiConnector

MODEL_ZH_SENT = "Chinese Sentence"

def clean_text(s):
    if not s:
        return ""
    # 1. Unescape HTML entities
    s = html.unescape(s)
    # 2. Strip HTML tags
    s = re.sub(r"<[^>]+>", "", s)
    # 3. Normalize quotes
    s = s.replace("‘", "'").replace("’", "'").replace("“", '"').replace("”", '"')
    return s.strip()

def clean_hanzi_sentence(s):
    s = clean_text(s)
    # Remove spaces between Chinese characters: e.g. "这个 多少钱?" -> "这个多少钱?"
    # Match Hanzi followed by whitespace followed by Hanzi
    hanzi_range = r"[\u4e00-\u9fff]"
    s = re.sub(rf"({hanzi_range})\s+({hanzi_range})", r"\1\2", s)
    s = re.sub(rf"({hanzi_range})\s+({hanzi_range})", r"\1\2", s) # twice for consecutive spaces
    # Remove space before punctuation: " 。" -> "。"
    s = re.sub(r"\s+([。？！，、；：?!,.])", r"\1", s)
    return s.strip()

def clean_pinyin(s):
    s = clean_text(s)
    # Collapse multiple spaces to single space
    s = re.sub(r"\s+", " ", s)
    return s.strip()

def run_clean():
    print(f"[*] Fetching notes for {MODEL_ZH_SENT}...")
    nids = AnkiConnector.invoke("findNotes", query=f"\"note:{MODEL_ZH_SENT}\"")
    print(f"  Total notes: {len(nids)}")
    
    notes = AnkiConnector.invoke("notesInfo", notes=nids)
    cleaned_count = 0
    
    for n in notes:
        nid = n["noteId"]
        flds = n["fields"]
        sent = flds.get("문장", {}).get("value", "")
        meaning = flds.get("뜻", {}).get("value", "")
        pinyin = flds.get("한어병음", {}).get("value", "")
        
        new_sent = clean_hanzi_sentence(sent)
        new_meaning = clean_text(meaning)
        new_pinyin = clean_pinyin(pinyin)
        
        if new_sent != sent or new_meaning != meaning or new_pinyin != pinyin:
            AnkiConnector.invoke("updateNoteFields", note={
                "id": nid,
                "fields": {
                    "문장": new_sent,
                    "뜻": new_meaning,
                    "한어병음": new_pinyin
                }
            })
            cleaned_count += 1
            
    print(f"✅ Finished! Cleaned {cleaned_count} out of {len(nids)} sentences.")

if __name__ == "__main__":
    run_clean()
