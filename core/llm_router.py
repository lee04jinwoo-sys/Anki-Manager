"""무료 등급 LLM을 정해진 순서대로 시도하고, 전부 실패하면 AllRoutesFailed를 던진다.

- 모든 경로는 OpenAI 호환 /chat/completions 엔드포인트다 (Gemini, Groq, Cerebras 모두 제공).
- 키가 환경 변수에 없는 경로는 요청 없이 건너뛴다. 키를 하나도 안 넣으면 곧바로 실패하고,
  호출하는 쪽(NoteCompleter)이 기존 유료 Gemini 키로 돌아간다. 즉 키를 넣기 전에는 동작이 그대로다.
- 429·5xx·타임아웃·연결 오류·깨진 JSON이면 다음 경로로 넘어간다.
- 순서와 모델은 data/settings.json의 LLM_FREE_ROUTES로 바꿀 수 있다
  ([{"name", "url", "model", "key_env"}, ...]).

모델 선택 원칙: 한국어 뜻·번역 품질이 중요하므로 작은 모델과 Llama 계열은 넣지 않는다.
기본 모델 이름은 2026-11-06 기준 각 회사 문서를 확인하지 않은 값이다 (미검증). 품질 비교 후 조정한다.
"""
from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass

import requests

from utils.settings_manager import get_setting

logger = logging.getLogger("llm_router")

ROUTE_TIMEOUT_SEC = 25  # 텔레그램 → 백엔드 대기 120초 안에 경로 3개 + 유료 키가 들어가도록


@dataclass(frozen=True)
class Route:
    name: str
    url: str
    model: str
    key_env: str


DEFAULT_ROUTES = [
    Route("gemini-free", "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
          "gemini-2.5-flash", "GEMINI_FREE_API_KEY"),
    Route("groq", "https://api.groq.com/openai/v1/chat/completions",
          "openai/gpt-oss-120b", "GROQ_API_KEY"),
    Route("cerebras", "https://api.cerebras.ai/v1/chat/completions",
          "gpt-oss-120b", "CEREBRAS_API_KEY"),
]


class AllRoutesFailed(Exception):
    pass


def load_routes():
    custom = get_setting("LLM_FREE_ROUTES", None)
    if not custom:
        return list(DEFAULT_ROUTES)
    return [Route(r["name"], r["url"], r["model"], r["key_env"]) for r in custom]


_FENCE = re.compile(r"^\s*```(?:json)?\s*(.*?)\s*```\s*$", re.DOTALL)


def _parse_json(text):
    if text is None:
        raise ValueError("empty content")
    m = _FENCE.match(text)
    if m:
        text = m.group(1)
    return json.loads(text, strict=False)


def generate_json(system, prompt, temperature, routes=None, post=None, env=None):
    """(파싱된 JSON, 응답한 경로 이름)을 돌려준다."""
    routes = load_routes() if routes is None else routes
    post = requests.post if post is None else post
    env = os.environ if env is None else env

    failures = []
    for route in routes:
        key = env.get(route.key_env)
        if not key:
            failures.append(f"{route.name}: no key")
            continue
        try:
            resp = post(
                route.url,
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json={
                    "model": route.model,
                    "messages": [{"role": "system", "content": system},
                                 {"role": "user", "content": prompt}],
                    "temperature": temperature,
                    "response_format": {"type": "json_object"},
                },
                timeout=ROUTE_TIMEOUT_SEC,
            )
            if resp.status_code != 200:
                raise RuntimeError(f"HTTP {resp.status_code}")
            content = resp.json()["choices"][0]["message"]["content"]
            data = _parse_json(content)
        except Exception as e:  # 어떤 실패든 다음 경로로
            logger.warning("LLM route %s failed: %s", route.name, e)
            failures.append(f"{route.name}: {e}")
            continue
        logger.info("LLM route %s (%s) answered", route.name, route.model)
        return data, route.name

    raise AllRoutesFailed("; ".join(failures) or "no routes")
