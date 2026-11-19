"""텔레그램 봇 스피킹 통합 테스트: 텍스트 기존 기능 무회귀 + /speak + 음성 + 인라인 버튼 + 예외 격리."""
from integrations import telegram_intake as ti

ALLOWED = 111


class FakeBackend:
    def __init__(self, routes=None):
        self.calls = []
        self.routes = dict(routes or {})

    def __call__(self, path, payload):
        self.calls.append((path, payload))
        fn = self.routes.get(path)
        if callable(fn):
            return fn(payload)
        if fn is not None:
            return fn
        return {"success": True, "note_id": 10, "data": {"word": "ok", "meaning": "오케이"}}


def test_existing_text_intake_unchanged_with_speaking_enabled():
    backend = FakeBackend({
        "/api/cards/vocab": {"success": True, "note_id": 1, "duplicate": False,
                             "data": {"word": "resilient", "meaning": "회복력 있는", "pos": "adj"}},
    })
    sent = []

    offset = ti.process_updates(
        [{"update_id": 1, "message": {"chat": {"id": ALLOWED}, "text": "resilient"}}],
        ALLOWED,
        backend,
        lambda chat_id, text, **kw: sent.append((chat_id, text, kw)),
    )

    assert offset == 2
    assert backend.calls == [("/api/cards/vocab", {"word": "resilient", "use_free_router": True})]
    assert "resilient" in sent[0][1]


def test_speak_command_starts_session_via_backend():
    backend = FakeBackend({
        "/api/speaking/start": {
            "step": "warmup_1",
            "message": "1/3 워밍업 시작",
            "candidates": [],
        },
    })
    sent = []

    offset = ti.process_updates(
        [{"update_id": 5, "message": {"chat": {"id": ALLOWED}, "text": "/speak interview"}}],
        ALLOWED,
        backend,
        lambda chat_id, text, **kw: sent.append((chat_id, text, kw)),
    )

    assert offset == 6
    assert backend.calls == [("/api/speaking/start", {"track": "interview"})]
    assert "1/3 워밍업 시작" in sent[0][1]


def test_voice_message_downloads_audio_posts_to_speaking_and_sends_reply_voice_and_buttons():
    backend = FakeBackend({
        "/api/speaking/voice": {
            "mode": "session",
            "step": "completed",
            "message": "세션 완료! Anki Speaking 1 -> 0",
            "audio_b64": "T0dHLUJZVEVT",  # base64("OGG-BYTES")
            "candidates": [
                {"id": 42, "kind": "sentence", "text": "That trade-off paid off."},
            ],
        },
    })
    sent_text = []
    sent_voice = []

    offset = ti.process_updates(
        [{
            "update_id": 10,
            "message": {
                "chat": {"id": ALLOWED},
                "voice": {"file_id": "FILE_123", "duration": 65},
            },
        }],
        ALLOWED,
        backend,
        lambda chat_id, text, **kw: sent_text.append((chat_id, text, kw)),
        download_file=lambda file_id: (b"RAW-OGG", "voice.ogg"),
        send_voice=lambda chat_id, audio_bytes, caption="": sent_voice.append((chat_id, audio_bytes, caption)),
    )

    assert offset == 11
    assert backend.calls[0][0] == "/api/speaking/voice"
    assert backend.calls[0][1]["filename"] == "voice.ogg"
    assert sent_text[0][1] == "세션 완료! Anki Speaking 1 -> 0"
    markup = sent_text[0][2]["reply_markup"]
    assert markup["inline_keyboard"][0][0]["callback_data"] == "spk_add:42"
    assert sent_voice == [(ALLOWED, b"OGG-BYTES", "원어민 대안 표현 듣기")]


def test_callback_query_registers_candidate_card_and_answers_callback():
    backend = FakeBackend({
        "/api/speaking/candidates/42/add": {
            "success": True,
            "note_id": 999,
            "message": "문장 카드 등록 완료 (speaking)",
        },
    })
    sent_text = []
    answered = []

    offset = ti.process_updates(
        [{
            "update_id": 20,
            "callback_query": {
                "id": "CB_1",
                "from": {"id": ALLOWED},
                "message": {"chat": {"id": ALLOWED}, "message_id": 55},
                "data": "spk_add:42",
            },
        }],
        ALLOWED,
        backend,
        lambda chat_id, text, **kw: sent_text.append((chat_id, text, kw)),
        answer_callback=lambda cb_id, text="": answered.append((cb_id, text)),
    )

    assert offset == 21
    assert backend.calls == [("/api/speaking/candidates/42/add", {})]
    assert answered == [("CB_1", "등록 완료")]
    assert "문장 카드 등록 완료" in sent_text[0][1]


def test_speaking_exception_is_isolated_and_offset_still_advances():
    def boom(_payload):
        raise RuntimeError("whisper timeout")

    backend = FakeBackend({"/api/speaking/voice": boom})
    sent = []

    offset = ti.process_updates(
        [{"update_id": 30, "message": {"chat": {"id": ALLOWED}, "voice": {"file_id": "F1"}}}],
        ALLOWED,
        backend,
        lambda chat_id, text, **kw: sent.append(text),
        download_file=lambda fid: (b"OGG", "voice.ogg"),
    )

    assert offset == 31
    assert sent and "오류" in sent[0]
