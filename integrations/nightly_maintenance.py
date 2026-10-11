"""밤 정리 작업 (텔레그램 Anki 봇으로 결과 알림).

빈 칸을 채우는 단계만 돌린다: 빈 필드(영어 노트 3종, 유의어 제외) → 오디오 → 품사.
덱 이동·중복 정리·템플릿처럼 구조를 바꾸거나 판단이 필요한 작업은 하지 않는다.
웹 화면과 같은 백엔드 작업(/api/organize/run)으로 돌려서 같은 작업 잠금을 쓴다.
빈 필드 대상이 field_cap을 넘으면 그 단계는 건너뛰고 알린다 (대량 변경·비용 방지).
채운 것이 있거나 실패했을 때만 알리고, 끝나면 AnkiWeb과 동기화한다.

실행 (systemd 타이머, 백업 뒤): .venv/bin/python -m integrations.nightly_maintenance
"""
from __future__ import annotations

import logging
import os
import time

import requests

logger = logging.getLogger("nightly_maintenance")

BACKEND_URL = os.environ.get("ANKI_MANAGER_URL", "http://127.0.0.1:8001")
FIELD_CAP = 100
POLL_SEC = 15
TIMEOUT_POLLS = 240  # 15초 × 240 = 1시간

# core.completer.run_universal_field_completion, AnkiTTSFiller, run_pos_automation 과 같은 조건
QUERIES = {
    "fields": ('(note:"English Sentence" "해설:") OR '
               '(note:"English Vocabulary" ("뜻:" OR "품사:" OR "예문:" OR "설명:")) OR '
               '(note:"English Grammar" ("해설:" OR "설명:" OR "보기1:" OR "보기2:" OR "보기3:"))'),
    "audio": ('("note:English Speaking" OR "note:English Grammar" OR "note:English Sentence" '
              'OR "note:English Vocabulary") "소리:"'),
    "pos": 'note:"English Vocabulary" "품사:"',
}
LABELS = {"fields": "빈 필드", "audio": "오디오", "pos": "품사"}
ORDER = ["fields", "audio", "pos"]


def _summary(before, after, skipped_fields):
    parts = []
    for step in ORDER:
        done = before[step] - after[step]
        if step == "fields" and skipped_fields:
            continue
        if before[step]:
            left = f" ({after[step]} 남음)" if after[step] else ""
            parts.append(f"{LABELS[step]} {done}{left}")
    return "🧹 Anki 밤 정리: " + ", ".join(parts)


def run(count, start, state, sync, send, sleep=time.sleep, field_cap=FIELD_CAP, timeout_polls=TIMEOUT_POLLS):
    before = count()
    skipped_fields = before["fields"] > field_cap
    if skipped_fields:
        send(f"⚠️ Anki 밤 정리: 빈 필드 대상 {before['fields']}개가 한도({field_cap})를 넘어 필드 단계를 건너뜀. "
             f"웹 화면 '노트 정리'에서 직접 확인해 주세요.")
    steps = [s for s in ORDER if before[s] and not (s == "fields" and skipped_fields)]
    if not steps:
        logger.info("할 일 없음: %s", before)
        return

    res = start(steps)
    if res.get("status") != "success":
        send(f"⚠️ Anki 밤 정리를 시작하지 못함: {res.get('message', '')}")
        return

    st = state()
    polls = 0
    while st.get("is_running"):
        polls += 1
        if polls >= timeout_polls:
            send("⚠️ Anki 밤 정리 시간 초과: 아직 실행 중입니다. 웹 화면에서 확인해 주세요.")
            return
        sleep(POLL_SEC)
        st = state()

    if st.get("status") != "success":
        last = " / ".join(l.get("message", "") for l in (st.get("logs") or [])[-3:])
        send(f"❌ Anki 밤 정리 실패 ({st.get('status')}): {last[:300]}")
        return

    after = count()
    send(_summary(before, after, skipped_fields))
    try:
        sync()
    except Exception as e:
        logger.warning("정리 후 동기화 실패: %s", e)


def _count():
    from integrations.anki_connect import AnkiConnector
    return {k: len(AnkiConnector.invoke("findNotes", query=q)) for k, q in QUERIES.items()}


def _start(steps):
    r = requests.post(f"{BACKEND_URL}/api/organize/run", json={"steps": steps}, timeout=60)
    r.raise_for_status()
    return r.json()


def _state():
    r = requests.get(f"{BACKEND_URL}/api/workflow/state", timeout=60)
    r.raise_for_status()
    return r.json()


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    from integrations import anki_sync
    notify = anki_sync.telegram_notifier()
    try:
        run(count=_count, start=_start, state=_state,
            sync=lambda: anki_sync.sync_and_report(anki_sync.anki_connect_sync, notify), send=notify)
    except Exception as e:
        logger.exception("밤 정리 실패")
        notify(f"❌ Anki 밤 정리 실패: {type(e).__name__}: {str(e)[:200]}")
        raise


if __name__ == "__main__":
    main()
