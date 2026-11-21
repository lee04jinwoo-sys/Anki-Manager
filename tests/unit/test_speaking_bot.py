"""integrations.speaking_bot 단위 테스트: 전용 봇 명령·음성·재녹음·FSRS 4버튼·후보 등록·권한 격리."""
from integrations import speaking_bot as sb

ALLOWED = 111


class FakeBackend:
    def __init__(self, routes=None):
        self.calls = []
        self.routes = dict(routes or {})

    def __call__(self, method, path, payload=None):
        self.calls.append((method, path, payload))
        fn = self.routes.get((method, path))
        if callable(fn):
            return fn(payload)
        if fn is not None:
            return fn
        return {"message": "ok", "candidates": []}


def test_today_command_starts_queue():
    backend = FakeBackend({
        ("POST", "/api/speaking/queue/start"): {
            "status": "question",
            "message": "오늘 총 2장\n[1/2] Campus\nExplain your major.",
            "candidates": [],
        }
    })
    sent = []

    offset = sb.process_updates(
        [{"update_id": 1, "message": {"chat": {"id": ALLOWED}, "text": "/today"}}],
        ALLOWED,
        backend,
        lambda cid, text, **kw: sent.append((cid, text, kw)),
    )

    assert offset == 2
    assert backend.calls == [("POST", "/api/speaking/queue/start", {})]
    assert "오늘 총 2장" in sent[0][1]


def test_voice_sends_feedback_tts_and_retry_plus_next_button():
    backend = FakeBackend({
        ("POST", "/api/speaking/voice"): {
            "mode": "card",
            "status": "evaluated",
            "card_id": 701,
            "recommended_ease": 3,
            "message": "WPM 118 · 필러 1회",
            "audio_b64": "T0dHLUJZVEVT",
            "candidates": [],
        }
    })
    sent_text = []
    sent_voice = []

    offset = sb.process_updates(
        [{"update_id": 2, "message": {"chat": {"id": ALLOWED}, "voice": {"file_id": "F1"}}}],
        ALLOWED,
        backend,
        lambda cid, text, **kw: sent_text.append((cid, text, kw)),
        download_file=lambda fid: (b"RAW-OGG", "v.ogg"),
        send_voice=lambda cid, data, caption="": sent_voice.append((cid, data, caption)),
    )

    assert offset == 3
    markup = sent_text[0][2]["reply_markup"]["inline_keyboard"]
    assert [b["callback_data"] for b in markup[0]] == ["spk_retry", "spk_rate:701:3"]
    assert "다음 질문" in markup[0][1]["text"]
    assert sent_voice == [(ALLOWED, b"OGG-BYTES", "원어민 모범 발화 듣기")]


def test_callbacks_retry_rate_and_add_candidate():
    backend = FakeBackend({
        ("POST", "/api/speaking/retry"): {"message": "같은 질문 재녹음 시작"},
        ("POST", "/api/speaking/rate"): {
            "status": "day_completed",
            "message": "오늘 스피킹 완료!",
            "candidates": [{"id": 9, "kind": "sentence", "text": "I major in CS."}],
        },
        ("POST", "/api/speaking/candidates/9/add"): {
            "success": True,
            "message": "문장 카드 등록 완료 (speaking)",
        },
    })
    sent = []
    answered = []

    updates = [
        {"update_id": 10, "callback_query": {"id": "C1", "from": {"id": ALLOWED}, "message": {"chat": {"id": ALLOWED}}, "data": "spk_retry"}},
        {"update_id": 11, "callback_query": {"id": "C2", "from": {"id": ALLOWED}, "message": {"chat": {"id": ALLOWED}}, "data": "spk_rate:701:3"}},
        {"update_id": 12, "callback_query": {"id": "C3", "from": {"id": ALLOWED}, "message": {"chat": {"id": ALLOWED}}, "data": "spk_add:9"}},
    ]

    offset = sb.process_updates(
        updates,
        ALLOWED,
        backend,
        lambda cid, text, **kw: sent.append((cid, text, kw)),
        answer_callback=lambda cb_id, text="": answered.append((cb_id, text)),
    )

    assert offset == 13
    assert [c[1] for c in backend.calls] == [
        "/api/speaking/retry",
        "/api/speaking/rate",
        "/api/speaking/candidates/9/add",
    ]
    assert backend.calls[1][2] == {"card_id": 701, "ease": 3}
    assert sent[1][2]["reply_markup"]["inline_keyboard"][0][0]["callback_data"] == "spk_add:9"
    assert len(answered) == 3


def test_unauthorized_chat_ignored_and_errors_isolated():
    def boom(_payload):
        raise RuntimeError("stt down")

    backend = FakeBackend({("POST", "/api/speaking/voice"): boom})
    sent = []

    offset = sb.process_updates(
        [
            {"update_id": 20, "message": {"chat": {"id": 999}, "text": "/today"}},
            {"update_id": 21, "message": {"chat": {"id": ALLOWED}, "voice": {"file_id": "F9"}}},
        ],
        ALLOWED,
        backend,
        lambda cid, text, **kw: sent.append((cid, text)),
        download_file=lambda fid: (b"OGG", "v.ogg"),
    )

    assert offset == 22
    assert len(backend.calls) == 1
    assert len(sent) == 1 and "오류" in sent[0][1]


def test_error_text_hides_non_backend_exception_details():
    class Boom(Exception):
        pass

    secret = "https://api.telegram.org/file/bot123:SECRET/voice.ogg"
    assert sb._safe_error(Boom(secret)) == "Boom"
    assert sb._safe_error(sb.BackendError("백엔드 연결 실패")) == "백엔드 연결 실패"


def test_long_message_is_split_under_telegram_limit_with_markup_on_last_chunk():
    sent = []
    text = "\n".join(f"line {i} " + "x" * 90 for i in range(120))  # ~11k chars
    sb._call_send(lambda cid, t, **kw: sent.append((t, kw)), ALLOWED, text, reply_markup={"inline_keyboard": []})

    assert len(sent) >= 3
    assert all(len(t) <= 4000 for t, _ in sent)
    assert "reply_markup" not in sent[0][1]
    assert "reply_markup" in sent[-1][1]
    assert "\n".join(t for t, _ in sent) == text


def test_evaluated_voice_sends_candidates_with_add_all_button():
    cands = [
        {"id": 11, "attempt_id": 7, "kind": "sentence", "text": "I mainly study biomolecular engineering."},
        {"id": 12, "attempt_id": 7, "kind": "vocab", "text": "derived from"},
    ]
    backend = FakeBackend({
        ("POST", "/api/speaking/voice"): {
            "status": "evaluated", "card_id": 701, "recommended_ease": 3, "message": "채점", "candidates": cands,
        },
        ("POST", "/api/speaking/attempts/7/candidates/add-all"): {"success": True, "message": "전부 추가: 2장 등록"},
    })
    sent = []
    send = lambda cid, text, **kw: sent.append((text, kw))
    sb.process_updates(
        [{"update_id": 5, "message": {"chat": {"id": ALLOWED}, "voice": {"file_id": "F"}}}],
        ALLOWED, backend, send, download_file=lambda fid: (b"x", "v.oga"), send_voice=lambda *a, **k: None,
    )
    assert sent[0][0] == "채점"
    rows = sent[1][1]["reply_markup"]["inline_keyboard"]
    assert [r[0]["callback_data"] for r in rows] == ["spk_add:11", "spk_add:12", "spk_addall:7"]
    assert "[표현]" in rows[1][0]["text"]

    sent.clear()
    sb.process_updates(
        [{"update_id": 6, "callback_query": {"id": "c", "from": {"id": ALLOWED},
          "message": {"chat": {"id": ALLOWED}}, "data": "spk_addall:7"}}],
        ALLOWED, backend, send, answer_callback=lambda *a, **k: None,
    )
    assert sent[0][0] == "전부 추가: 2장 등록"


def test_next_command_calls_next_endpoint():
    backend = FakeBackend({("POST", "/api/speaking/next"): {"status": "question", "message": "Q2?", "candidates": []}})
    sent = []
    sb.process_updates(
        [{"update_id": 9, "message": {"chat": {"id": ALLOWED}, "text": "/next"}}],
        ALLOWED, backend, lambda cid, text, **kw: sent.append(text),
    )
    assert backend.calls[0][:2] == ("POST", "/api/speaking/next")
    assert sent == ["Q2?"]
