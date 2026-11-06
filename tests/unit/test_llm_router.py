"""무료 등급 모델부터 차례로 시도하는 LLM 라우터.

실제 네트워크에는 붙지 않는다. HTTP 호출(post)과 환경 변수(env)를 가짜로 바꿔 끼운다.
"""
import json

import pytest
import requests

from core import llm_router
from core.llm_router import AllRoutesFailed, Route, generate_json

ROUTES = [
    Route("free-a", "https://a.example/v1/chat/completions", "model-a", "KEY_A"),
    Route("free-b", "https://b.example/v1/chat/completions", "model-b", "KEY_B"),
]
ENV = {"KEY_A": "ka", "KEY_B": "kb"}


class FakeResponse:
    def __init__(self, status, content=None):
        self.status_code = status
        self._content = content

    def json(self):
        return {"choices": [{"message": {"content": self._content}}]}


class FakePost:
    """URL마다 미리 정한 응답(또는 예외)을 돌려주고 호출을 기록한다."""

    def __init__(self, by_url):
        self.by_url = by_url
        self.calls = []

    def __call__(self, url, headers=None, json=None, timeout=None):
        self.calls.append({"url": url, "headers": headers, "json": json, "timeout": timeout})
        result = self.by_url[url]
        if isinstance(result, Exception):
            raise result
        return result


def _ok(obj):
    return FakeResponse(200, json.dumps(obj, ensure_ascii=False))


def test_first_route_answers():
    post = FakePost({ROUTES[0].url: _ok({"뜻": "행운"})})

    data, used = generate_json("sys", "prompt", 0.3, routes=ROUTES, post=post, env=ENV)

    assert data == {"뜻": "행운"}
    assert used == "free-a"
    assert len(post.calls) == 1


def test_rate_limited_route_falls_through_to_next():
    post = FakePost({ROUTES[0].url: FakeResponse(429), ROUTES[1].url: _ok({"뜻": "행운"})})

    data, used = generate_json("sys", "prompt", 0.3, routes=ROUTES, post=post, env=ENV)

    assert used == "free-b"
    assert data == {"뜻": "행운"}


def test_broken_json_falls_through_to_next():
    post = FakePost({ROUTES[0].url: FakeResponse(200, "죄송하지만 {뜻: 행운"),
                     ROUTES[1].url: _ok({"뜻": "행운"})})

    _, used = generate_json("sys", "prompt", 0.3, routes=ROUTES, post=post, env=ENV)

    assert used == "free-b"


def test_timeout_falls_through_to_next():
    post = FakePost({ROUTES[0].url: requests.Timeout("slow"), ROUTES[1].url: _ok({"뜻": "행운"})})

    _, used = generate_json("sys", "prompt", 0.3, routes=ROUTES, post=post, env=ENV)

    assert used == "free-b"


def test_route_without_key_is_skipped_without_request():
    post = FakePost({ROUTES[1].url: _ok({"뜻": "행운"})})

    _, used = generate_json("sys", "prompt", 0.3, routes=ROUTES, post=post, env={"KEY_B": "kb"})

    assert used == "free-b"
    assert [c["url"] for c in post.calls] == [ROUTES[1].url]


def test_all_routes_failing_raises():
    post = FakePost({ROUTES[0].url: FakeResponse(500), ROUTES[1].url: FakeResponse(429)})

    with pytest.raises(AllRoutesFailed):
        generate_json("sys", "prompt", 0.3, routes=ROUTES, post=post, env=ENV)


def test_no_keys_at_all_raises_without_requests():
    post = FakePost({})

    with pytest.raises(AllRoutesFailed):
        generate_json("sys", "prompt", 0.3, routes=ROUTES, post=post, env={})
    assert post.calls == []


def test_request_carries_key_model_json_mode_and_messages():
    post = FakePost({ROUTES[0].url: _ok({"x": 1})})

    generate_json("시스템", "질문", 0.3, routes=ROUTES, post=post, env=ENV)

    call = post.calls[0]
    assert call["headers"]["Authorization"] == "Bearer ka"
    assert call["json"]["model"] == "model-a"
    assert call["json"]["temperature"] == 0.3
    assert call["json"]["response_format"] == {"type": "json_object"}
    assert call["json"]["messages"] == [{"role": "system", "content": "시스템"},
                                        {"role": "user", "content": "질문"}]
    assert call["timeout"]


def test_code_fenced_json_is_accepted():
    post = FakePost({ROUTES[0].url: FakeResponse(200, '```json\n{"뜻": "행운"}\n```')})

    data, _ = generate_json("sys", "prompt", 0.3, routes=ROUTES, post=post, env=ENV)

    assert data == {"뜻": "행운"}


def test_routes_can_be_overridden_from_settings(monkeypatch):
    monkeypatch.setattr(llm_router, "get_setting", lambda key, default: [
        {"name": "custom", "url": "https://c.example/v1/chat/completions", "model": "m", "key_env": "KEY_C"}
    ] if key == "LLM_FREE_ROUTES" else default)

    routes = llm_router.load_routes()

    assert routes == [Route("custom", "https://c.example/v1/chat/completions", "m", "KEY_C")]


def test_free_flash_lite_backs_up_free_flash():
    """2026-11-06 서버 실측: 무료 키 gemini-2.5-flash는 503(high demand)이 잦고,
    같은 키의 flash-lite는 3/3 성공. flash 다음에 무료 flash-lite를 둔다 (유료 키와 같은 모델)."""
    first, second = llm_router.DEFAULT_ROUTES[:2]
    assert (first.model, first.key_env) == ("gemini-2.5-flash", "GEMINI_FREE_API_KEY")
    assert (second.model, second.key_env) == ("gemini-2.5-flash-lite", "GEMINI_FREE_API_KEY")


def test_default_routes_contain_no_llama():
    """한국어 품질이 약한 Llama 계열은 기본 목록에 넣지 않는다."""
    assert all("llama" not in r.model.lower() for r in llm_router.DEFAULT_ROUTES)
