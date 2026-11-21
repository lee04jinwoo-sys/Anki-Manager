import pytest

from speaking.morning_push import push_morning_queue


class _Resp:
    def __init__(self, status=200, body=None):
        self.status_code = status
        self._body = body or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._body


def test_backend_failure_notifies_telegram_then_raises():
    sent = []

    def post(url, json=None, timeout=None):
        sent.append((url, json))
        return _Resp(500) if "queue/start" in url else _Resp(200)

    with pytest.raises(RuntimeError):
        push_morning_queue("TOKEN", 1, post=post, backend_url="http://x")

    assert len(sent) == 2
    assert "api.telegram.org" in sent[1][0]
    assert "불러오지 못했습니다" in sent[1][1]["text"]
    assert "TOKEN" not in sent[1][1]["text"]


def test_success_sends_queue_message():
    def post(url, json=None, timeout=None):
        return _Resp(200, {"message": "Q1"}) if "queue/start" in url else _Resp(200)

    out = push_morning_queue("TOKEN", 1, post=post, backend_url="http://x")
    assert out["message"] == "Q1"
