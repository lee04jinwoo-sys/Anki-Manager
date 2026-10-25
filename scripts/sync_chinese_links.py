"""
Sync existing Chinese Sentence cards into Chinese Vocabulary note examples.
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

MODEL_ZH_VOCAB = "Chinese Vocabulary"
MODEL_ZH_SENT = "Chinese Sentence"

# Common functional 1-char words to skip to avoid noisy over-matching
STOP_1CHAR = set("的了我你他在是有就不吗吧呢很也都")

def run_sync():
    print(f"[*] Loading notes from {MODEL_ZH_VOCAB} and {MODEL_ZH_SENT}...")
    vocab_nids = AnkiConnector.invoke("findNotes", query=f"\"note:{MODEL_ZH_VOCAB}\"")
    sent_nids = AnkiConnector.invoke("findNotes", query=f"\"note:{MODEL_ZH_SENT}\"")
    
    print(f"  Vocab count: {len(vocab_nids)}, Sentence count: {len(sent_nids)}")
    
    vocab_notes = AnkiConnector.invoke("notesInfo", notes=vocab_nids)
    sent_notes = AnkiConnector.invoke("notesInfo", notes=sent_nids)
    
    # Prepare clean sentences
    sentences = []
    for s in sent_notes:
        f = s["fields"]
        text = f.get("문장", {}).get("value", "").strip()
        pinyin = f.get("한어병음", {}).get("value", "").strip()
        meaning = f.get("뜻", {}).get("value", "").strip()
        if text:
            formatted = f"{text} ({pinyin} / {meaning})"
            sentences.append({
                "id": s["noteId"],
                "text": text,
                "formatted": formatted
            })
            
    matched_count = 0
    updated_vocab_count = 0
    
    for v in vocab_notes:
        nid = v["noteId"]
        f = v["fields"]
        word = f.get("단어", {}).get("value", "").strip()
        ex = f.get("예문", {}).get("value", "").strip()
        
        if not word:
            continue
            
        # 1-char stopword filter
        if len(word) == 1 and word in STOP_1CHAR:
            continue
            
        existing_list = [s.strip() for s in ex.split("|||") if s.strip()]
        new_matches = []
        
        for s in sentences:
            if word in s["text"]:
                # Check if this sentence text is already in existing examples
                if not any(s["text"] in exist for exist in existing_list):
                    new_matches.append(s["formatted"])
                    
        if new_matches:
            all_examples = existing_list + new_matches
            # Keep max 4 examples per vocab
            final_ex = " ||| ".join(all_examples[:4])
            AnkiConnector.invoke("updateNoteFields", note={
                "id": nid,
                "fields": {"예문": final_ex}
            })
            matched_count += len(new_matches)
            updated_vocab_count += 1
            
    print(f"✅ Sync complete! Linked {matched_count} sentence occurrences to {updated_vocab_count} vocab cards.")

if __name__ == "__main__":
    run_sync()
