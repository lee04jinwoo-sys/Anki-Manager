"""
Update Tier 1 vocabulary notes:
1. Replace 'someone', 'something' placeholders with 'A' (e.g. 'work something out' -> 'work A out')
2. Add 'be' to predicate idioms/adjectival phrases (e.g. 'not all there' -> 'be not all there')
3. Regenerate TTS sound tags and re-index in LinkManager.
"""

import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from integrations.anki_connect import AnkiConnector
from integrations.audio import AnkiTTSFiller
from core.link_manager import LinkManager

# Exact mapping of Note ID -> (new_word, new_meaning_optional)
UPDATES = [
    # 1. Placeholders: someone / something -> A
    (1792807618199, "work A out", "A를 해결하다, 타협점을 찾다"),
    (1789688510009, "give A shit", "A를 갈구다, 트집 잡다, 괴롭히다"),
    (1792807620774, "get A out of one's system", "A에 대한 미련을 털어내다"),

    # 2. Add 'be ' to predicate phrases
    (1792807611349, "be not all there", None),
    (1792807606050, "be all up with", None),
    (1792807607149, "be in the can", None),
    (1792807609274, "be on the up and up", None),
    (1792807609774, "be up and about", None),
    (1792807624999, "be up to no good", None),
    (1790866972062, "be out of focus", None),
    (1708413816651, "be out of control", None),
    (1759323937314, "be on the same page", None),
    (1752736638431, "be on the house", None),
    (1737452044409, "be on the rise", None),
    (1751848967900, "be in between jobs", None),
    (1770278812619, "be in a meeting", None),
    (1756436164855, "be in charge of A", None),
    (1746682232638, "be on sale", None),
    (1751848967868, "be worth it", None),
    (1742386471563, "be up to A", None),
    (1785660613952, "be right around the corner", None),
]


def run():
    print(f"=== Updating {len(UPDATES)} vocabulary notes in Anki ===")

    # Release any active editor lock in Anki
    try:
        os.system("osascript -e 'tell application \"Anki\" to activate' -e 'tell application \"System Events\" to key code 53'")
        cards = AnkiConnector.invoke("findCards", query='"deck:1. Language::1.1. English::Vocabulary"')
        if cards:
            AnkiConnector.invoke("guiSelectCard", card=cards[0])
    except Exception as e:
        print(f"Lock release notice: {e}")

    success_count = 0

    for nid, new_word, new_meaning in UPDATES:
        info_list = AnkiConnector.invoke("notesInfo", notes=[nid])
        if not info_list:
            print(f"[-] Note {nid} not found, skipping.")
            continue
        note = info_list[0]
        fields = note["fields"]
        old_word = fields["단어"]["value"]
        old_meaning = fields["뜻"]["value"]
        pos = fields.get("품사", {}).get("value", "idiom")

        meaning = new_meaning if new_meaning else old_meaning

        # Audio generation: For phrases with placeholder 'A', voice natural text
        voice_text = new_word.replace(" A's", "").replace(" A", "").replace(" B", "").strip()
        sound_tag, _ = AnkiTTSFiller.generate_gtts(voice_text)

        update_fields = {
            "단어": new_word,
            "뜻": meaning,
            "소리": sound_tag,
        }

        try:
            AnkiConnector.invoke(
                "updateNoteFields",
                note={"id": nid, "fields": update_fields}
            )
            try:
                LinkManager.index_single_vocab(nid, new_word, meaning, pos)
            except Exception as le:
                print(f"    Link indexing warning: {le}")

            print(f"[✓] {nid}: '{old_word}' -> '{new_word}' (sound: {sound_tag})")
            success_count += 1
        except Exception as e:
            print(f"[x] Failed to update {nid}: {e}")

    print(f"\n✅ Completed: {success_count}/{len(UPDATES)} notes updated successfully.")


if __name__ == "__main__":
    run()
