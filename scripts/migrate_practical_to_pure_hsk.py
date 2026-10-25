"""
Migrate all 'hsk::practical' tags to pure HSK 1~6 levels for complete HSK standardization.
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


def main():
    print("[*] Fetching official HSK dataset...")
    url = "https://raw.githubusercontent.com/drkameleon/complete-hsk-vocabulary/main/complete.json"
    req_hsk = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    hsk_list = json.loads(urllib.request.urlopen(req_hsk, timeout=15).read().decode("utf-8"))

    hsk2_map = {}
    char_map = {}
    for item in hsk_list:
        hz = item.get("simplified")
        if not hz:
            continue
        levels = item.get("level", [])
        for lvl in levels:
            if lvl.startswith("new-"):
                try:
                    l_num = int(lvl.replace("new-", ""))
                    if hz not in hsk2_map or l_num < hsk2_map[hz]:
                        hsk2_map[hz] = l_num
                    if len(hz) == 1:
                        if hz not in char_map or l_num < char_map[hz]:
                            char_map[hz] = l_num
                except Exception:
                    pass

    def get_word_hsk(word: str) -> int:
        if word in hsk2_map:
            return hsk2_map[word]
        if word.endswith("儿") and word[:-1] in hsk2_map:
            return hsk2_map[word[:-1]]
        if (word + "儿") in hsk2_map:
            return hsk2_map[word + "儿"]
        # Known compounds
        if any(k in word for k in ["星期", "一百", "一千", "一万", "一个", "两个", "三个", "四个", "五个", "这个", "那个", "不是", "什么时候", "这位"]):
            return 1
        if any(k in word for k in ["上个", "下个", "几天", "两天", "十天", "点菜", "每天", "第一", "火车站", "小狗", "骑自行车", "洗脸", "羊肉", "中午饭", "不知道"]):
            return 2
        if any(k in word for k in ["买单", "餐巾纸", "茶水", "打羽毛球", "理发店", "蛋糕", "草莓", "逛街", "玩游戏", "泡菜", "炸鸡", "电风扇"]):
            return 3
        lvls = [char_map.get(c, 3) for c in word if c in char_map]
        if lvls:
            return min(max(lvls), 4)
        return 3

    # 1. Update Vocabulary notes
    print("[*] Finding vocab notes with 'hsk::practical'...")
    nids = AnkiConnector.invoke("findNotes", query='"note:Chinese Vocabulary" tag:hsk::practical')
    notes = AnkiConnector.invoke("notesInfo", notes=nids)
    print(f"  ✓ Found {len(notes)} vocab notes to migrate.")

    for n in notes:
        nid = n["noteId"]
        word = n["fields"]["단어"]["value"]
        lvl = get_word_hsk(word)
        new_tag = f"hsk::{lvl}"
        AnkiConnector.invoke("removeTags", notes=[nid], tags="hsk::practical")
        AnkiConnector.invoke("addTags", notes=[nid], tags=new_tag)

    print(f"  ✓ Successfully migrated {len(notes)} vocab notes to pure HSK tags.")

    # 2. Update Sentence notes
    print("[*] Finding sentence notes with 'hsk::practical'...")
    sent_nids = AnkiConnector.invoke("findNotes", query='"note:Chinese Sentence" tag:hsk::practical')
    sent_notes = AnkiConnector.invoke("notesInfo", notes=sent_nids)
    print(f"  ✓ Found {len(sent_notes)} sentence notes to migrate.")

    sent_manual_map = {
        "这个多少钱?": 1,
        "太贵，请便宜点。": 2,
        "水是自助吗？": 2,
        "可以给餐巾纸吗？": 2,
        "可以推荐好吃的饭店吗?": 3,
        "可以用信用卡结算吗?": 3,
    }

    for n in sent_notes:
        nid = n["noteId"]
        s = n["fields"]["문장"]["value"]
        lvl = sent_manual_map.get(s, 2)
        new_tag = f"hsk::{lvl}"
        AnkiConnector.invoke("removeTags", notes=[nid], tags="hsk::practical")
        AnkiConnector.invoke("addTags", notes=[nid], tags=new_tag)

    print(f"  ✓ Successfully migrated {len(sent_notes)} sentence notes to pure HSK tags.")
    print("\n✅ All practical tags eliminated! Complete HSK 1~6 standardization achieved.")


if __name__ == "__main__":
    main()
