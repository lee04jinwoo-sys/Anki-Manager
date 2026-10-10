import json
import logging
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from backend.services.corpus_service import CorpusService
from backend.schemas.corpus import PromoteChunkRequest

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("Batch2Promote")

def run_batch_2_promote():
    curated_path = BASE_DIR / "data" / "batch_2_promote_curated.json"
    with open(curated_path, "r", encoding="utf-8") as f:
        items = json.load(f)

    logger.info(f"[*] Starting Batch 2 Promotion for {len(items)} curated chunk items...")
    
    success_count = 0
    fail_count = 0

    for idx, it in enumerate(items):
        note_id = it["note_id"]
        chunk = it["chunk"]
        pos = it["pos"]
        meaning = it["meaning"]

        req = PromoteChunkRequest(
            note_id=note_id,
            new_chunk=chunk,
            meaning=meaning,
            pos=pos,
            example_1=it["example_1"],
            trans_1=it["trans_1"],
            example_2=it["example_2"],
            trans_2=it["trans_2"],
            explanation=it.get("explanation", ""),
            add_sentences_to_deck=True,
            reset_to_new=True
        )

        try:
            res = CorpusService.promote_chunk(req)
            if res.success:
                success_count += 1
                logger.info(f"[{idx+1:2d}/{len(items)}] ✓ Note {note_id}: '{it['original_word']}' -> '{chunk}' [{pos}] (Reset: {res.cards_reset_count}, Sentences: {res.sentences_added_count})")
            else:
                fail_count += 1
                logger.error(f"[{idx+1:2d}/{len(items)}] ✗ Note {note_id} failed: {res.error}")
        except Exception as e:
            fail_count += 1
            logger.error(f"[{idx+1:2d}/{len(items)}] ✗ Exception promoting note {note_id}: {e}")

    logger.info(f"\n[+] Batch 2 promotion completed! Success: {success_count}/{len(items)}, Failed: {fail_count}")

if __name__ == "__main__":
    run_batch_2_promote()
