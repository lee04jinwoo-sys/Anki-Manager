"""아침 브리핑과 저녁 리마인더 (텔레그램 Anki 봇).

숫자는 대시보드와 같은 백엔드 통계 API(/api/stats/overview)에서 가져온다. 읽기 전에 서버 Anki를
AnkiWeb과 동기화해 휴대폰 복습을 반영한다. 저녁 리마인더는 오늘 리뷰가 0일 때만 보낸다.

실행 (systemd 타이머, 토론토 시각): .venv/bin/python -m integrations.daily_brief morning|evening
"""
from __future__ import annotations

import datetime
import logging
import os
import sys

import requests

logger = logging.getLogger("daily_brief")

BACKEND_URL = os.environ.get("ANKI_MANAGER_URL", "http://127.0.0.1:8001")


def _yesterday(ov):
    today = datetime.date.fromisoformat(ov["today"]["date"])
    target = (today - datetime.timedelta(days=1)).isoformat()
    for day in ov.get("heatmap") or []:
        if day.get("date") == target:
            return day.get("reviews", 0), day.get("minutes", 0.0)
    return 0, 0.0


def format_morning(ov):
    t = ov["today"]
    y_reviews, y_minutes = _yesterday(ov)
    lines = [f"☀️ 오늘 복습 {t['due_remaining']}장 · 새 카드 가능 {t['new_available']}장",
             f"어제 {y_reviews}장 ({y_minutes:.0f}분) · 연속 {ov['habit']['current']}일"]
    rate = ((ov.get("retention_30d") or {}).get("all") or {}).get("rate")
    if rate is not None:
        lines.append(f"30일 정답률 {rate:.1f}%")
    return "\n".join(lines)


def format_evening(ov):
    t = ov["today"]
    if t["reviews"] > 0:
        return None
    return (f"🌙 오늘 아직 복습 기록이 없어요. 남은 복습 {t['due_remaining']}장, "
            f"연속 {ov['habit']['current']}일이 이어지려면 오늘 해야 해요.\n"
            f"(휴대폰에서 이미 했다면 그쪽 동기화가 아직 안 된 것일 수 있어요)")


def run(kind, fetch, sync, send):
    if kind not in ("morning", "evening"):
        raise ValueError(kind)
    try:
        sync()
    except Exception as e:  # 동기화가 안 돼도 브리핑은 보낸다 (실패 알림은 anki_sync가 따로 한다)
        logger.warning("브리핑 전 동기화 실패: %s", e)
    try:
        ov = fetch()
        text = format_morning(ov) if kind == "morning" else format_evening(ov)
    except Exception as e:
        logger.exception("통계 조회 실패")
        text = f"⚠️ Anki {'아침 브리핑' if kind == 'morning' else '저녁 리마인더'} 실패: {type(e).__name__}: {str(e)[:150]}"
    if text:
        send(text)


def _fetch_overview():
    r = requests.get(f"{BACKEND_URL}/api/stats/overview", timeout=120)
    r.raise_for_status()
    return r.json()


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    from integrations import anki_sync
    notify = anki_sync.telegram_notifier()
    run(sys.argv[1],
        fetch=_fetch_overview,
        sync=lambda: anki_sync.sync_and_report(anki_sync.anki_connect_sync, notify),
        send=notify)


if __name__ == "__main__":
    main()
