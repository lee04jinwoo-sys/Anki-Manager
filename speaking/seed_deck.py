"""One-shot CLI to configure the `English Speaking` preset, remove legacy tracker, and seed 72 Daily cards."""
from __future__ import annotations

import logging

from integrations import anki_sync
from speaking.anki_deck import AnkiSpeakingDeck
from speaking.question_bank import DAILY_QUESTIONS

logger = logging.getLogger("speaking.seed_deck")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    deck = AnkiSpeakingDeck()
    preset = deck.ensure_speaking_deck_and_preset()
    removed = deck.remove_legacy_tracker_card()
    seeded = deck.seed_daily_questions(DAILY_QUESTIONS)
    counts = deck.get_deck_counts()

    logger.info("Preset: %s", preset)
    logger.info("Legacy tracker notes removed: %d", removed)
    logger.info("Seeded daily questions: %s", seeded)
    logger.info("Deck counts: %s", counts.model_dump())

    anki_sync.anki_connect_sync()
    logger.info("AnkiWeb sync complete.")


if __name__ == "__main__":
    main()
