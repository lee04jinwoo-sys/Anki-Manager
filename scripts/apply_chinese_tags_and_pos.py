"""
Apply official HSK difficulty tags, English POS conversion, and HTML cleanup to Chinese notes.
"""

import json
import os
import re
import sys
import urllib.request
from pathlib import Path

os.environ["no_proxy"] = "*"
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from integrations.anki_connect import AnkiConnector

POS_MAP = {
    '동사': 'v', '명사': 'n', '형용사': 'adj', '부사': 'adv',
    '대명사': 'pron', '수사': 'num', '양사': 'mw', '전치사': 'prep',
    '개사': 'prep', '접속사': 'conj', '연사': 'conj', '조동사': 'aux',
    '조사': 'part', '감탄사': 'int', '어구': 'idiom', '명사구': 'n', '문장': 'idiom'
}

def clean_html(text: str) -> str:
    return re.sub(r'<[^>]+>', '', text).strip()

def convert_pos(pos_str: str) -> str:
    parts = [p.strip() for p in pos_str.split(',') if p.strip()]
    en_parts = []
    for p in parts:
        en = POS_MAP.get(p, p.lower())
        if en not in en_parts:
            en_parts.append(en)
    return ', '.join(en_parts) if en_parts else 'n'

def main():
    print("[*] Fetching official HSK dataset...")
    url = 'https://raw.githubusercontent.com/drkameleon/complete-hsk-vocabulary/main/complete.json'
    req_hsk = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    hsk_list = json.loads(urllib.request.urlopen(req_hsk, timeout=15).read().decode('utf-8'))

    hsk2_map = {}
    for item in hsk_list:
        hz = item.get('simplified')
        if not hz:
            continue
        levels = item.get('level', [])
        for lvl in levels:
            if lvl.startswith('new-'):
                try:
                    l_num = int(lvl.replace('new-', ''))
                    if hz not in hsk2_map or l_num < hsk2_map[hz]:
                        hsk2_map[hz] = l_num
                except Exception:
                    pass

    print(f"  ✓ Loaded {len(hsk2_map)} HSK words mapping.")

    # 1. Update Chinese Vocabulary notes
    print("[*] Loading Chinese Vocabulary notes...")
    vocab_nids = AnkiConnector.invoke("findNotes", query='"note:Chinese Vocabulary"')
    vocab_notes = AnkiConnector.invoke("notesInfo", notes=vocab_nids)
    print(f"  ✓ Found {len(vocab_notes)} vocab notes.")

    updated_fields_count = 0
    tags_added_count = 0

    for n in vocab_notes:
        nid = n['noteId']
        raw_word = n['fields']['단어']['value']
        word = clean_html(raw_word)
        raw_pos = n['fields']['품사']['value']
        new_pos = convert_pos(raw_pos)

        # 1. Clean HTML in 단어 and convert 품사
        fields_to_update = {}
        if raw_word != word:
            fields_to_update['단어'] = word
        if raw_pos != new_pos:
            fields_to_update['품사'] = new_pos

        if fields_to_update:
            AnkiConnector.invoke("updateNoteFields", note={"id": nid, "fields": fields_to_update})
            updated_fields_count += 1

        # 2. Add HSK Tag
        lvl = hsk2_map.get(word)
        tag = f"hsk::{lvl}" if lvl else "hsk::practical"
        existing_tags = n.get('tags', [])
        if tag not in existing_tags:
            AnkiConnector.invoke("addTags", notes=[nid], tags=tag)
            tags_added_count += 1

    print(f"  ✓ Updated fields for {updated_fields_count} vocab notes.")
    print(f"  ✓ Added HSK tags to {tags_added_count} vocab notes.")

    # 2. Update Chinese Sentence notes (Tag based on complexity)
    print("[*] Loading Chinese Sentence notes...")
    sent_nids = AnkiConnector.invoke("findNotes", query='"note:Chinese Sentence"')
    sent_notes = AnkiConnector.invoke("notesInfo", notes=sent_nids)
    print(f"  ✓ Found {len(sent_notes)} sentence notes.")

    for n in sent_notes:
        nid = n['noteId']
        sent = n['fields']['문장']['value']
        # Simple heuristic: <=6 chars -> hsk::1, >6 chars -> hsk::2, travel/shopping -> hsk::practical
        if any(k in sent for k in ['多少钱', '信用卡', '餐巾纸', '便宜', '饭店', '自助']):
            tag = "hsk::practical"
        elif len(sent) <= 7:
            tag = "hsk::1"
        else:
            tag = "hsk::2"

        existing_tags = n.get('tags', [])
        if tag not in existing_tags:
            AnkiConnector.invoke("addTags", notes=[nid], tags=tag)

    print("  ✓ Tagged sentence notes.")
    print("\n✅ All Chinese notes successfully updated with English POS and HSK tags!")


if __name__ == "__main__":
    main()
