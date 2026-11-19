"""Daily 04:05 America/Toronto job: reset the 1 Anki Speaking tracker card to Due (1) and sync."""
from __future__ import annotations

import logging
import os

import requests

logger = logging.getLogger("speaking.daily_reset")

BACKEND_URL = os.environ.get("ANKI_MANAGER_URL", "http://127.0.0.1:8001")


def reset_via_backend(post=requests.post, backend_url: str = BACKEND_URL):
    resp = post(f"{backend_url}/api/speaking/tracker/reset", json={}, timeout=60)
    resp.raise_for_status()
    return resp.json()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    from integrations import anki_sync

    notify = anki_sync.telegram_notifier()
    try:
        res = reset_via_backend()
        logger.info("Speaking tracker reset complete: %s", res)
        anki_sync.sync_and_report(anki_sync.anki_connect_sync, notify)
    except Exception as e:
        logger.exception("Speaking daily tracker reset failed")
        notify(f"⚠️ Anki Speaking 일일 리셋 실패: {type(e).__name__}: {str(e)[:200]}")
        raise


if __name__ == "__main__":
    main()
