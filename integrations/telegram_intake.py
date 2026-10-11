"""텔레그램으로 보낸 단어·문장을 Anki 카드로 등록하고 결과를 답장한다.

마침표(. ? !)로 끝나면 문장 카드, 아니면 단어 카드. 등록은 같은 서버의 Anki Manager
백엔드 API를 부른다 (웹 화면과 같은 규칙·링크 색인을 쓰기 위해). 허락된 채팅만 받는다.

실행: TELEGRAM_BOT_TOKEN, TELEGRAM_ALLOWED_CHAT_ID 환경 변수를 두고
    .venv/bin/python -m integrations.telegram_intake
"""
from __future__ import annotations

import datetime
import json
import logging
import os
import time
from pathlib import Path
import threading

import requests

from integrations import anki_sync

logger = logging.getLogger("telegram_intake")

BACKEND_URL = os.environ.get("ANKI_MANAGER_URL", "http://127.0.0.1:8001")
SENTENCE_ENDINGS = (".", "?", "!")
USAGE = ("단어는 그대로, 문장은 마침표(. ? !)로 끝내서 보내 주세요. 여러 줄로 보내면 줄마다 등록해요.\n"
         "/undo: 방금 넣은 카드 지우기")
MAX_LINES = 20
UNDO_WINDOW = datetime.timedelta(hours=24)
HISTORY_PATH = Path(__file__).resolve().parents[1] / "data" / "telegram_added.json"
_POLL_TIMEOUT_SEC = 50
# 등록은 Gemini 보강·TTS까지 기다리므로 넉넉히
_BACKEND_TIMEOUT_SEC = 120


class BackendError(Exception):
    pass


def classify(text):
    body = (text or "").strip()
    if not body:
        return None
    return ("sentence" if body.endswith(SENTENCE_ENDINGS) else "vocab"), body


def _format_reply(kind, res):
    data = res.get("data") or {}
    label = "문장" if kind == "sentence" else "단어"
    if res.get("duplicate"):
        return f"이미 있는 {label} 카드입니다: {data.get('word') or data.get('sentence') or ''}".rstrip()
    if not res.get("success"):
        return f"❌ 등록 실패: {res.get('error') or '알 수 없는 오류'}"
    if kind == "sentence":
        return f"✅ 문장 카드 등록\n{data.get('sentence', '')}\n→ {data.get('translation') or '(번역 없음)'}"
    pos = f" ({data['pos']})" if data.get("pos") else ""
    return f"✅ 단어 카드 등록\n{data.get('word', '')}{pos} — {data.get('meaning') or '(뜻 없음)'}"


def _register(body, post_backend):
    """한 줄을 등록한다. (답장 문자열, 새 카드인지, note_id)를 돌려준다."""
    kind, body = classify(body)
    path, payload = (("/api/cards/sentence", {"sentence": body}) if kind == "sentence"
                     else ("/api/cards/vocab", {"word": body}))
    try:
        res = post_backend(path, payload)
    except Exception as e:  # 한 줄의 실패가 봇 전체를 멈추지 않게
        logger.exception("카드 등록 실패: %s", body)
        return f"❌ 등록 실패: {e}", False, None
    created = bool(res.get("success")) and not res.get("duplicate")
    return _format_reply(kind, res), created, res.get("note_id")


def _safe_call(fn, what):
    if not fn:
        return
    try:
        fn()
    except Exception:
        logger.exception("%s 실패", what)


def handle_text(text, chat_id, allowed_chat_id, post_backend, on_added=None, history=None, undo=None):
    """답장할 문자열을 돌려준다. 허락되지 않은 채팅이면 None (무시).

    여러 줄이면 줄마다 따로 등록하고 답장 하나로 모은다 (최대 MAX_LINES줄).
    새 카드가 하나라도 생기면 on_added()를 한 번 부른다 (AnkiWeb 동기화용). /undo는 undo()로 처리한다.
    """
    if chat_id != allowed_chat_id:
        logger.warning("허락되지 않은 채팅 %s 무시", chat_id)
        return None
    stripped = (text or "").strip()
    if stripped.split("@")[0] == "/undo" and undo is not None:
        reply = undo()
        if reply.startswith("🗑"):
            _safe_call(on_added, "삭제 후 동기화")
        return reply
    lines = [l.strip() for l in stripped.splitlines() if l.strip()]
    # /start 같은 텔레그램 명령은 카드로 만들지 않는다
    if not lines or lines[0].startswith("/"):
        return USAGE
    if len(lines) > MAX_LINES:
        return f"한 번에 {MAX_LINES}줄까지 보낼 수 있어요 ({len(lines)}줄 받음). 나눠서 보내 주세요."

    replies, added = [], 0
    for line in lines:
        reply, created, note_id = _register(line, post_backend)
        replies.append(reply)
        if created:
            added += 1
            if history is not None and note_id:
                history.push(note_id, line)
    if added:
        _safe_call(on_added, "등록 후 처리")
    if len(lines) == 1:
        return replies[0]
    return f"📥 {len(lines)}줄 처리 (새 카드 {added}장)\n\n" + "\n\n".join(replies)


class AddedHistory:
    """봇으로 새로 넣은 카드 목록 (/undo용). 봇이 재시작돼도 남도록 파일에 둔다."""
    MAX = 50

    def __init__(self, path):
        self.path = Path(path)

    def entries(self):
        try:
            data = json.loads(self.path.read_text())
            return data if isinstance(data, list) else []
        except (OSError, ValueError):
            return []

    def _save(self, entries):
        self.path.write_text(json.dumps(entries[-self.MAX:], ensure_ascii=False))

    def push(self, note_id, label):
        self._save(self.entries() + [{"note_id": note_id, "label": label}])

    def pop(self):
        entries = self.entries()
        if entries:
            entries.pop()
            self._save(entries)


def undo_last(history, anki, now):
    """마지막으로 넣은 카드를 지운다. 복습했거나 24시간이 지났으면 지우지 않는다."""
    entries = history.entries()
    if not entries:
        return "되돌릴 카드가 없어요 (봇으로 넣은 카드만 되돌릴 수 있어요)."
    last = entries[-1]
    note_id, label = last["note_id"], last["label"]
    reps = anki.reps(note_id)
    if reps is None:
        history.pop()
        return f"'{label}'은(는) 이미 Anki에서 지워져 목록에서만 뺐어요. 한 번 더 보내면 그 전 카드를 되돌려요."
    if reps > 0:
        return f"'{label}'은(는) 복습 기록이 있어 지우지 않았어요. 필요하면 Anki에서 직접 지워 주세요."
    age = now - datetime.datetime.fromtimestamp(note_id / 1000, tz=datetime.timezone.utc)
    if age > UNDO_WINDOW:
        return f"'{label}'은(는) 넣은 지 24시간이 지나 지우지 않았어요. 필요하면 Anki에서 직접 지워 주세요."
    anki.delete(note_id)
    history.pop()
    return f"🗑 삭제: {label}"


class AnkiForUndo:
    """undo_last가 쓰는 AnkiConnect 호출."""

    @staticmethod
    def reps(note_id):
        from integrations.anki_connect import AnkiConnector
        info = AnkiConnector.invoke("notesInfo", notes=[note_id])
        if not info or not info[0] or not info[0].get("cards"):
            return None
        cards = AnkiConnector.invoke("cardsInfo", cards=info[0]["cards"])
        return sum(c.get("reps", 0) for c in cards)

    @staticmethod
    def delete(note_id):
        from core.link_manager import LinkManager
        from integrations.anki_connect import AnkiConnector
        AnkiConnector.invoke("deleteNotes", notes=[note_id])
        # 링크 색인과, 문장 등록 때 단어 카드 '예문'에 덧붙인 문장도 되돌린다
        LinkManager.remove_note(note_id)


def process_updates(updates, allowed_chat_id, post_backend, send, on_added=None, history=None, undo=None):
    """업데이트 묶음을 처리하고 다음 offset을 돌려준다. 실패한 메시지도 건너뛴다 (재처리 반복 방지)."""
    offset = None
    for upd in updates:
        offset = upd["update_id"] + 1
        msg = upd.get("message") or {}
        text = msg.get("text")
        chat_id = (msg.get("chat") or {}).get("id")
        if text is None or chat_id is None:
            continue
        reply = handle_text(text, chat_id, allowed_chat_id, post_backend, on_added, history, undo)
        if reply is not None:
            try:
                send(chat_id, reply)
            except Exception as e:
                # 예외 메시지에 토큰이 든 URL이 담길 수 있어 종류만 남긴다
                logger.warning("답장 전송 실패: %s", type(e).__name__)
    return offset


def _post_backend(path, payload):
    try:
        r = requests.post(BACKEND_URL + path, json=payload, timeout=_BACKEND_TIMEOUT_SEC)
    except requests.RequestException as e:
        raise BackendError(f"백엔드 연결 실패 ({type(e).__name__})") from e
    if r.status_code >= 400:
        try:
            detail = r.json().get("detail")
        except ValueError:
            detail = r.text[:200]
        raise BackendError(str(detail))
    return r.json()


def run(token, allowed_chat_id):
    api = f"https://api.telegram.org/bot{token}"
    session = requests.Session()

    def send(chat_id, text):
        session.post(f"{api}/sendMessage", json={"chat_id": chat_id, "text": text}, timeout=30)

    notify = anki_sync.telegram_notifier()

    def sync_in_background():
        # 답장을 늦추지 않도록 따로 돌린다. AnkiConnect가 요청을 차례로 처리하므로 겹쳐도 안전하다.
        threading.Thread(target=anki_sync.sync_and_report,
                         args=(anki_sync.anki_connect_sync, notify), daemon=True).start()

    history = AddedHistory(HISTORY_PATH)
    undo = lambda: undo_last(history, AnkiForUndo, datetime.datetime.now(datetime.timezone.utc))

    offset = None
    logger.info("텔레그램 폴링 시작 (허락된 채팅 %s)", allowed_chat_id)
    while True:
        try:
            r = session.get(f"{api}/getUpdates",
                            params={"timeout": _POLL_TIMEOUT_SEC, "offset": offset, "allowed_updates": '["message"]'},
                            timeout=_POLL_TIMEOUT_SEC + 10)
            updates = r.json().get("result", [])
        except Exception as e:
            # 토큰이 URL에 들어 있으니 예외 메시지를 그대로 남기지 않는다
            logger.warning("getUpdates 실패: %s", type(e).__name__)
            time.sleep(5)
            continue
        new_offset = process_updates(updates, allowed_chat_id, _post_backend, send, sync_in_background,
                                     history, undo)
        if new_offset is not None:
            offset = new_offset


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    # requests/urllib3 디버그 로그에 토큰 URL이 찍히지 않게
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    run(os.environ["TELEGRAM_BOT_TOKEN"], int(os.environ["TELEGRAM_ALLOWED_CHAT_ID"]))


if __name__ == "__main__":
    main()
