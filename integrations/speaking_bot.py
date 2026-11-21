"""전용 영어 스피킹 텔레그램 봇 (`SPEAKING_BOT_TOKEN`).

Anki `1. Language::1.1. English::Speaking` FSRS 큐와 1:1로 연동하여
아침 푸시·질문 출제·음성 채점·재녹음·Again/Hard/Good/Easy 평가·하루 요약을 처리한다.

실행: SPEAKING_BOT_TOKEN, TELEGRAM_ALLOWED_CHAT_ID 환경 변수를 두고
    .venv/bin/python -m integrations.speaking_bot
"""
from __future__ import annotations

import base64
import logging
import os
import time
from pathlib import Path

import requests

logger = logging.getLogger("speaking_bot")

BACKEND_URL = os.environ.get("ANKI_MANAGER_URL", "http://127.0.0.1:8001")
_POLL_TIMEOUT_SEC = 50
_BACKEND_TIMEOUT_SEC = 120

USAGE = (
    "영어 스피킹 전용 봇 (Anki `Speaking` 덱 FSRS 연동)\n"
    "/today : 오늘의 스피킹 큐 시작/이어하기\n"
    "/skip : 다음 카드로 순서 넘기기\n"
    "/summary : 오늘 말한 세트 요약 & 카드 후보 보기\n"
    "/last : 최근 답변의 문장별 교정 보기\n"
    "/stats : 스트릭 · 최근 14일 WPM/필러 통계\n"
    "/debrief : 외부 대화 막힌 표현 회수 (큐 완료 후엔 음성을 바로 보내도 자동 회수)"
)

_EASE_BUTTONS = (
    (1, "Again"),
    (2, "Hard"),
    (3, "Good"),
    (4, "Easy"),
)


class BackendError(Exception):
    pass


def _safe_error(e):
    """백엔드 오류 문구는 그대로, 그 외(requests 등)는 URL에 봇 토큰이 섞일 수 있어 타입만 노출한다."""
    return str(e) if isinstance(e, BackendError) else type(e).__name__


def _build_evaluation_markup(card_id, recommended_ease):
    rate_row = []
    for ease, label in _EASE_BUTTONS:
        text = f"★ {label}" if ease == recommended_ease else label
        rate_row.append({"text": text, "callback_data": f"spk_rate:{card_id}:{ease}"})
    return {
        "inline_keyboard": [
            [{"text": "🔄 재녹음 (같은 질문)", "callback_data": "spk_retry"}],
            rate_row,
        ]
    }


def _build_candidate_markup(candidates):
    if not candidates:
        return None
    kind_label = {"sentence": "문장", "vocab": "표현", "grammar": "문법"}
    rows = []
    for c in candidates:
        cid = c.get("id")
        if cid is None:
            continue
        k = kind_label.get(c.get("kind", "sentence"), "문장")
        preview = (c.get("text") or "").strip()
        if len(preview) > 36:
            preview = preview[:33] + "..."
        rows.append([{"text": f"+ [{k}] {preview}", "callback_data": f"spk_add:{cid}"}])
    if not rows:
        return None
    attempt_id = next((c.get("attempt_id") for c in candidates if c.get("attempt_id") is not None), None)
    if len(rows) > 1 and attempt_id is not None:
        rows.append([{"text": f"+ 전부 추가 ({len(rows)}장)", "callback_data": f"spk_addall:{attempt_id}"}])
    return {"inline_keyboard": rows}


_TG_LIMIT = 4000  # 텔레그램 메시지 상한 4096자에 여유를 둔다


def _split_text(text, limit=_TG_LIMIT):
    chunks, cur = [], ""
    for line in text.split("\n"):
        while len(line) > limit:
            if cur:
                chunks.append(cur)
                cur = ""
            chunks.append(line[:limit])
            line = line[limit:]
        if cur and len(cur) + 1 + len(line) > limit:
            chunks.append(cur)
            cur = line
        else:
            cur = f"{cur}\n{line}" if cur else line
    if cur:
        chunks.append(cur)
    return chunks or [""]


def _call_send(send, chat_id, text, reply_markup=None):
    chunks = _split_text(text)
    for i, chunk in enumerate(chunks):
        if reply_markup is not None and i == len(chunks) - 1:
            send(chat_id, chunk, reply_markup=reply_markup)
        else:
            send(chat_id, chunk)


def _send_action_response(res, chat_id, send, send_voice=None):
    markup = None
    candidates = res.get("candidates") or []
    evaluated = res.get("status") == "evaluated" and res.get("card_id") is not None
    if evaluated:
        markup = _build_evaluation_markup(res["card_id"], res.get("recommended_ease"))
    elif candidates:
        markup = _build_candidate_markup(candidates)

    _call_send(send, chat_id, res.get("message") or "완료", reply_markup=markup)

    audio_b64 = res.get("audio_b64")
    if audio_b64 and send_voice:
        try:
            send_voice(chat_id, base64.b64decode(audio_b64), "원어민 모범 발화 듣기")
        except Exception as e:
            logger.warning("음성 답장 전송 실패: %s", type(e).__name__)

    if evaluated and candidates:
        cand_markup = _build_candidate_markup(candidates)
        if cand_markup:
            _call_send(send, chat_id, "Anki에 넣을 후보 (누르면 문장/단어 덱에 추가)", reply_markup=cand_markup)


def _handle_command(text, chat_id, backend, send):
    cmd = text.strip().split()[0].split("@")[0].lower()
    if cmd in ("/start", "/today"):
        res = backend("POST", "/api/speaking/queue/start", {})
        _send_action_response(res, chat_id, send)
    elif cmd == "/skip":
        res = backend("POST", "/api/speaking/skip", {})
        _send_action_response(res, chat_id, send)
    elif cmd == "/summary":
        res = backend("GET", "/api/speaking/summary", None)
        _send_action_response(res, chat_id, send)
    elif cmd == "/last":
        res = backend("GET", "/api/speaking/last", None)
        _send_action_response(res, chat_id, send)
    elif cmd == "/stats":
        res = backend("GET", "/api/speaking/stats", None)
        _call_send(send, chat_id, res.get("message") or "통계 없음")
    elif cmd == "/debrief":
        _call_send(send, chat_id, "방금 외부 대화에서 막혔던 상황이나 표현을 30~60초 음성으로 보내 주세요.")
    else:
        _call_send(send, chat_id, USAGE)


def _handle_voice(voice_obj, chat_id, backend, send, download_file, send_voice):
    if not download_file:
        _call_send(send, chat_id, "음성 다운로드 핸들러가 설정되지 않았습니다.")
        return
    file_id = voice_obj.get("file_id")
    if not file_id:
        return
    audio_bytes, filename = download_file(file_id)
    res = backend(
        "POST",
        "/api/speaking/voice",
        {
            "audio_b64": base64.b64encode(audio_bytes).decode("ascii"),
            "filename": filename or "voice.ogg",
        },
    )
    _send_action_response(res, chat_id, send, send_voice=send_voice)


def _handle_callback(cb, allowed_chat_id, backend, send, answer_callback):
    cb_id = cb.get("id")
    chat_id = ((cb.get("message") or {}).get("chat") or {}).get("id")
    from_id = (cb.get("from") or {}).get("id")
    if chat_id != allowed_chat_id and from_id != allowed_chat_id:
        return
    target_chat = chat_id or from_id
    data = (cb.get("data") or "").strip()

    if data == "spk_retry":
        res = backend("POST", "/api/speaking/retry", {})
        if answer_callback and cb_id:
            answer_callback(cb_id, "재녹음 준비")
        _call_send(send, target_chat, res.get("message") or "같은 질문을 다시 녹음해 보내세요.")
        return

    if data.startswith("spk_rate:"):
        _, card_str, ease_str = data.split(":", 2)
        res = backend("POST", "/api/speaking/rate", {"card_id": int(card_str), "ease": int(ease_str)})
        if answer_callback and cb_id:
            answer_callback(cb_id, "Anki 반영 완료")
        _send_action_response(res, target_chat, send)
        return

    if data.startswith("spk_addall:"):
        attempt_id = data.split(":", 1)[1]
        res = backend("POST", f"/api/speaking/attempts/{attempt_id}/candidates/add-all", {})
        ok = bool(res.get("success"))
        if answer_callback and cb_id:
            answer_callback(cb_id, "등록 완료" if ok else "일부 실패")
        _call_send(send, target_chat, res.get("message") or ("등록 완료" if ok else "등록 실패"))
        return

    if data.startswith("spk_add:"):
        cand_id = data.split(":", 1)[1]
        res = backend("POST", f"/api/speaking/candidates/{cand_id}/add", {})
        ok = bool(res.get("success"))
        if answer_callback and cb_id:
            answer_callback(cb_id, "등록 완료" if ok else "등록 실패")
        _call_send(send, target_chat, res.get("message") or ("등록 완료" if ok else "등록 실패"))


def process_updates(
    updates,
    allowed_chat_id,
    backend,
    send,
    download_file=None,
    send_voice=None,
    answer_callback=None,
):
    offset = None
    for upd in updates:
        offset = upd["update_id"] + 1
        cb = upd.get("callback_query")
        if cb:
            try:
                _handle_callback(cb, allowed_chat_id, backend, send, answer_callback)
            except Exception as e:
                logger.warning("콜백 처리 오류: %s", type(e).__name__)
                chat_id = ((cb.get("message") or {}).get("chat") or {}).get("id")
                if chat_id == allowed_chat_id:
                    _call_send(send, chat_id, f"버튼 처리 오류: {_safe_error(e)}")
            continue

        msg = upd.get("message") or {}
        chat_id = (msg.get("chat") or {}).get("id")
        if chat_id != allowed_chat_id:
            continue

        voice_obj = msg.get("voice") or msg.get("audio")
        if voice_obj:
            try:
                _handle_voice(voice_obj, chat_id, backend, send, download_file, send_voice)
            except Exception as e:
                logger.warning("음성 처리 오류: %s", type(e).__name__)
                _call_send(send, chat_id, f"음성 처리 오류: {_safe_error(e)}")
            continue

        text = msg.get("text")
        if text:
            try:
                _handle_command(text, chat_id, backend, send)
            except Exception as e:
                logger.warning("명령 처리 오류: %s", type(e).__name__)
                _call_send(send, chat_id, f"요청 처리 오류: {_safe_error(e)}")
    return offset


def _backend_request(method, path, payload=None):
    try:
        if method == "GET":
            r = requests.get(BACKEND_URL + path, timeout=_BACKEND_TIMEOUT_SEC)
        else:
            r = requests.post(BACKEND_URL + path, json=payload or {}, timeout=_BACKEND_TIMEOUT_SEC)
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
    file_api = f"https://api.telegram.org/file/bot{token}"
    session = requests.Session()

    def send(chat_id, text, reply_markup=None):
        body = {"chat_id": chat_id, "text": text}
        if reply_markup is not None:
            body["reply_markup"] = reply_markup
        session.post(f"{api}/sendMessage", json=body, timeout=30)

    def send_voice(chat_id, audio_bytes, caption=""):
        session.post(
            f"{api}/sendVoice",
            data={"chat_id": chat_id, "caption": caption[:200]},
            files={"voice": ("feedback.ogg", audio_bytes, "audio/ogg")},
            timeout=30,
        )

    def answer_callback(callback_query_id, text=""):
        session.post(
            f"{api}/answerCallbackQuery",
            json={"callback_query_id": callback_query_id, "text": text},
            timeout=15,
        )

    def download_file(file_id):
        meta = session.get(f"{api}/getFile", params={"file_id": file_id}, timeout=20).json()
        file_path = (meta.get("result") or {}).get("file_path")
        if not file_path:
            raise RuntimeError("텔레그램 파일 경로 조회 실패")
        raw = session.get(f"{file_api}/{file_path}", timeout=45)
        raw.raise_for_status()
        return raw.content, Path(file_path).name

    offset = None
    logger.info("스피킹 텔레그램 봇 폴링 시작 (허락된 채팅 %s)", allowed_chat_id)
    while True:
        try:
            r = session.get(
                f"{api}/getUpdates",
                params={
                    "timeout": _POLL_TIMEOUT_SEC,
                    "offset": offset,
                    "allowed_updates": '["message","callback_query"]',
                },
                timeout=_POLL_TIMEOUT_SEC + 10,
            )
            body = r.json()
            if not body.get("ok"):
                # 409(봇 인스턴스 중복)·401 등은 즉시 반환되므로 쉬지 않으면 API를 계속 두드린다.
                logger.warning("getUpdates 거부: %s %s", r.status_code, body.get("description", ""))
                time.sleep(5)
                continue
            updates = body.get("result", [])
        except Exception as e:
            logger.warning("getUpdates 실패: %s", type(e).__name__)
            time.sleep(5)
            continue
        new_offset = process_updates(
            updates,
            allowed_chat_id,
            _backend_request,
            send,
            download_file=download_file,
            send_voice=send_voice,
            answer_callback=answer_callback,
        )
        if new_offset is not None:
            offset = new_offset


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    run(os.environ["SPEAKING_BOT_TOKEN"], int(os.environ["TELEGRAM_ALLOWED_CHAT_ID"]))


if __name__ == "__main__":
    main()
