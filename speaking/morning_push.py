"""Daily 09:00 America/Toronto push: sync AnkiWeb, pull today's Speaking queue, send question [1/N]."""
from __future__ import annotations

import logging
import os

import requests

logger = logging.getLogger("speaking.morning_push")

BACKEND_URL = os.environ.get("ANKI_MANAGER_URL", "http://127.0.0.1:8001")


def push_morning_queue(
    token: str,
    chat_id: int,
    sync_fn=None,
    post=requests.post,
    backend_url: str = BACKEND_URL,
) -> dict:
    if sync_fn is not None:
        try:
            sync_fn()
        except Exception as e:
            logger.warning("아침 푸시 전 Anki 동기화 경고: %s", e)

    tg_url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        resp = post(f"{backend_url}/api/speaking/queue/start", json={}, timeout=60)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        logger.error("아침 큐 로드 실패: %s", type(e).__name__)
        try:
            post(
                tg_url,
                json={
                    "chat_id": chat_id,
                    "text": f"⚠️ 오늘 스피킹 큐를 불러오지 못했습니다 ({type(e).__name__}). 서버나 Mac Anki 연결을 확인하세요.",
                },
                timeout=30,
            )
        except Exception:
            logger.error("실패 알림 전송도 실패")
        raise

    msg = data.get("message") or "오늘 스피킹 큐 확인 완료"
    r = post(
        tg_url,
        json={"chat_id": chat_id, "text": f"☀️ 09:00 영어 스피킹 큐\n\n{msg}"},
        timeout=30,
    )
    r.raise_for_status()
    return data


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    token = os.environ.get("SPEAKING_BOT_TOKEN", "").strip()
    chat_raw = os.environ.get("TELEGRAM_ALLOWED_CHAT_ID", "").strip()
    if not token or not chat_raw:
        logger.warning("SPEAKING_BOT_TOKEN 또는 TELEGRAM_ALLOWED_CHAT_ID가 비어 있어 아침 푸시를 건너뜁니다.")
        return

    push_morning_queue(token=token, chat_id=int(chat_raw))


if __name__ == "__main__":
    main()
