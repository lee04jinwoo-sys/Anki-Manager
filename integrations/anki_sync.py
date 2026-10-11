"""서버 Anki를 AnkiWeb과 동기화하고, 실패하면 텔레그램으로 알린다.

AnkiConnect `sync`는 전체 동기화(업로드/다운로드 선택)가 필요하면 아무것도 덮어쓰지 않고
오류를 낸다. 그때는 사용자가 VNC로 직접 골라야 하므로 알림으로 알려 준다.
같은 실패가 이어지는 동안은 다시 알리지 않고, 복구되면 한 번 알린다.

실행 (systemd 타이머): .venv/bin/python -m integrations.anki_sync
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path

import requests

logger = logging.getLogger("anki_sync")

STATE_PATH = Path(__file__).resolve().parents[1] / "data" / "sync_state.json"


def _describe(exc):
    msg = str(exc)
    if "Sync status" in msg:
        return ("⚠️ Anki 전체 동기화가 필요합니다. 자동으로 덮어쓰지 않았습니다.\n"
                "VNC로 서버 Anki를 열고 Sync를 눌러 직접 선택해 주세요 (보통은 AnkiWeb에서 다운로드).\n"
                f"원문: {msg[:200]}")
    return f"⚠️ 서버 Anki 동기화 실패: {msg[:300]}"


def _load_state(path):
    try:
        return json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return {}


def _save_state(path, state):
    try:
        Path(path).write_text(json.dumps(state, ensure_ascii=False))
    except OSError:
        logger.exception("동기화 상태 저장 실패")


def _safe_notify(notify, text):
    try:
        notify(text)
    except Exception as e:
        logger.warning("동기화 알림 전송 실패: %s", e)


def sync_and_report(sync, notify, state_path=None):
    """동기화를 한 번 실행한다. 성공하면 True."""
    state_path = state_path or STATE_PATH  # 호출 시점에 읽는다 (테스트가 경로를 바꿔 끼울 수 있게)
    state = _load_state(state_path)
    last_error = state.get("last_error")
    try:
        sync()
    except Exception as e:
        text = _describe(e)
        logger.warning("동기화 실패: %s", e)
        if text != last_error:
            _safe_notify(notify, text)
        _save_state(state_path, {"last_error": text})
        return False
    logger.info("동기화 성공")
    if last_error:
        _safe_notify(notify, "✅ 서버 Anki 동기화가 복구됐습니다.")
    _save_state(state_path, {"last_error": None})
    return True


def anki_connect_sync():
    from integrations.anki_connect import AnkiConnector
    AnkiConnector.invoke("sync")


def telegram_notifier():
    """환경 변수가 없으면 로그만 남기는 알림 함수를 돌려준다."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_ALLOWED_CHAT_ID")
    if not token or not chat_id:
        return lambda text: logger.warning("텔레그램 설정 없음, 알림 생략: %s", text)

    def notify(text):
        # 예외 메시지에 토큰이 든 URL이 담기므로 종류만 남긴다
        try:
            r = requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                              json={"chat_id": int(chat_id), "text": text}, timeout=30)
        except requests.RequestException as e:
            raise RuntimeError(f"telegram sendMessage failed ({type(e).__name__})") from None
        if r.status_code >= 400:
            raise RuntimeError(f"telegram sendMessage HTTP {r.status_code}")
    return notify


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    sync_and_report(anki_connect_sync, telegram_notifier())


if __name__ == "__main__":
    main()
