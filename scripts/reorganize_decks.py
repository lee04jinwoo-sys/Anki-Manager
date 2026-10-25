"""
Reorganize Anki Decks:
1. Move Japanese, Hanja, Chess to 3. Etc (Archive mode: 0 new, 0 rev)
2. Split Chinese into 1. Language::1.3. Chinese::Vocabulary and Sentence
"""

import os
import sys
from pathlib import Path

os.environ["no_proxy"] = "*"
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from integrations.anki_connect import AnkiConnector

def run():
    print("[1/4] Configuring 3. Etc Deck Config to Archive Mode (0 new / 0 review)...")
    etc_cfg = AnkiConnector.invoke("getDeckConfig", deck="3. Etc")
    etc_cfg["new"]["perDay"] = 0
    etc_cfg["rev"]["perDay"] = 0
    AnkiConnector.invoke("saveDeckConfig", config=etc_cfg)
    etc_config_id = etc_cfg["id"]
    print(f"  Config {etc_config_id} updated: new.perDay=0, rev.perDay=0")

    # 1. Move Japanese
    print("\n[2/4] Moving Japanese and Hanja to 3. Etc...")
    jap_cards = AnkiConnector.invoke("findCards", query='"deck:1. Language::1.2. Japanese"')
    if jap_cards:
        AnkiConnector.invoke("createDeck", deck="3. Etc::Japanese")
        AnkiConnector.invoke("changeDeck", cards=jap_cards, deck="3. Etc::Japanese")
        AnkiConnector.invoke("setDeckConfigId", decks=["3. Etc::Japanese"], configId=etc_config_id)
        print(f"  Moved {len(jap_cards)} Japanese cards to '3. Etc::Japanese'")

    hanja_cards = AnkiConnector.invoke("findCards", query='"deck:1. Language::1.4. Hanja"')
    if hanja_cards:
        AnkiConnector.invoke("createDeck", deck="3. Etc::Hanja")
        AnkiConnector.invoke("changeDeck", cards=hanja_cards, deck="3. Etc::Hanja")
        AnkiConnector.invoke("setDeckConfigId", decks=["3. Etc::Hanja"], configId=etc_config_id)
        print(f"  Moved {len(hanja_cards)} Hanja cards to '3. Etc::Hanja'")

    # Move Chess
    print("\n[3/4] Moving Chess decks to 3. Etc...")
    chess_cards = AnkiConnector.invoke("findCards", query='"deck:Chess" -deck:"Chess::*"')
    if chess_cards:
        AnkiConnector.invoke("createDeck", deck="3. Etc::Chess")
        AnkiConnector.invoke("changeDeck", cards=chess_cards, deck="3. Etc::Chess")
        AnkiConnector.invoke("setDeckConfigId", decks=["3. Etc::Chess"], configId=etc_config_id)
        print(f"  Moved {len(chess_cards)} Chess cards to '3. Etc::Chess'")

    chess_puzzles_cards = AnkiConnector.invoke("findCards", query='"deck:Chess::Puzzles"')
    if chess_puzzles_cards:
        AnkiConnector.invoke("createDeck", deck="3. Etc::Chess::Puzzles")
        AnkiConnector.invoke("changeDeck", cards=chess_puzzles_cards, deck="3. Etc::Chess::Puzzles")
        AnkiConnector.invoke("setDeckConfigId", decks=["3. Etc::Chess::Puzzles"], configId=etc_config_id)
        print(f"  Moved {len(chess_puzzles_cards)} Chess::Puzzles cards to '3. Etc::Chess::Puzzles'")

    # Clean old empty decks
    print("\n  Cleaning up empty legacy decks...")
    try:
        AnkiConnector.invoke("deleteDecks", decks=[
            "1. Language::1.2. Japanese",
            "1. Language::1.4. Hanja",
            "Chess::Puzzles",
            "Chess"
        ], cardsToo=False)
        print("  Deleted old empty decks.")
    except Exception as e:
        print(f"  Deck cleanup notice: {e}")

    # 4. Split Chinese into Vocabulary and Sentence
    print("\n[4/4] Splitting Chinese into Vocabulary and Sentence subdecks...")
    AnkiConnector.invoke("createDeck", deck="1. Language::1.3. Chinese::Vocabulary")
    AnkiConnector.invoke("createDeck", deck="1. Language::1.3. Chinese::Sentence")

    zh_vocab_cards = AnkiConnector.invoke("findCards", query='"note:Chinese Vocabulary" "deck:1. Language::1.3. Chinese"')
    if zh_vocab_cards:
        AnkiConnector.invoke("changeDeck", cards=zh_vocab_cards, deck="1. Language::1.3. Chinese::Vocabulary")
        print(f"  Moved {len(zh_vocab_cards)} Chinese Vocabulary cards to '1. Language::1.3. Chinese::Vocabulary'")

    zh_sent_cards = AnkiConnector.invoke("findCards", query='"note:Chinese Sentence" "deck:1. Language::1.3. Chinese"')
    if zh_sent_cards:
        AnkiConnector.invoke("changeDeck", cards=zh_sent_cards, deck="1. Language::1.3. Chinese::Sentence")
        print(f"  Moved {len(zh_sent_cards)} Chinese Sentence cards to '1. Language::1.3. Chinese::Sentence'")

    print("\n✅ Deck reorganization complete!")

if __name__ == "__main__":
    run()
