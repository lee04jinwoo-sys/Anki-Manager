"""읽기 전용 비교: 연결 없는 단어 N개로 Gemini Flash-Lite vs 로컬 llama-server 예문 생성.

Anki·links.db에 쓰지 않는다 (links.db는 읽기 전용 URI로 연다).
실행 (서버, ~/anki-manager에서): .venv/bin/python scripts/compare_local_llm.py --n 20 --out ~/llm/compare.json
"""
import argparse
import json
import sqlite3
import sys
import time

import requests

sys.path.insert(0, ".")
from core.batch_generator import BATCH_SENTENCE_PROMPT  # noqa: E402


def pick_words(n, seed):
    con = sqlite3.connect("file:data/links.db?mode=ro", uri=True)
    rows = con.execute(
        "SELECT note_id, word, meaning FROM vocab_cache WHERE link_count = 0 ORDER BY note_id").fetchall()
    import random
    rnd = random.Random(seed)
    return [dict(note_id=r[0], word=r[1], meaning=r[2] or "") for r in rnd.sample(rows, n)]


def user_prompt(words):
    # batch_generator.generate_and_add_sentences와 같은 프롬프트 구성
    lines = []
    for item in words:
        short_m = item["meaning"].strip().split(",")[0].split(";")[0].split("(")[0].strip()[:20]
        lines.append(f"- {item['word']}" + (f" ({short_m})" if short_m else ""))
    return "다음 어휘들로 실생활 예문과 번역을 생성해 주세요:\n" + "\n".join(lines)


def run_gemini(prompt):
    from google import genai
    from google.genai import types
    from config import GOOGLE_API_KEY
    client = genai.Client(api_key=GOOGLE_API_KEY)
    t = time.time()
    r = client.models.generate_content(
        model="gemini-2.5-flash-lite", contents=prompt,
        config=types.GenerateContentConfig(system_instruction=BATCH_SENTENCE_PROMPT, temperature=0.3,
                                           response_mime_type="application/json"))
    um = r.usage_metadata
    return dict(seconds=round(time.time() - t, 1), raw=r.text,
                tokens=dict(prompt=um.prompt_token_count, output=um.candidates_token_count))


def run_local(prompt, url):
    t = time.time()
    r = requests.post(f"{url}/v1/chat/completions", timeout=3600, json=dict(
        messages=[{"role": "system", "content": BATCH_SENTENCE_PROMPT}, {"role": "user", "content": prompt}],
        temperature=0.3, response_format={"type": "json_object"}))
    r.raise_for_status()
    d = r.json()
    return dict(seconds=round(time.time() - t, 1), raw=d["choices"][0]["message"]["content"],
                tokens=dict(prompt=d["usage"]["prompt_tokens"], output=d["usage"]["completion_tokens"]),
                timings=d.get("timings"))


def parse(raw):
    try:
        items = json.loads(raw)
    except Exception as e:
        return None, f"JSON 파싱 실패: {e}"
    if isinstance(items, dict):
        items = next((v for v in items.values() if isinstance(v, list)), [])
    out = []
    for it in items:
        if isinstance(it, (list, tuple)) and len(it) >= 3:
            out.append(dict(word=it[0], sentence=it[1], translation=it[2]))
        elif isinstance(it, dict):
            out.append(dict(word=it.get("word", ""), sentence=it.get("sentence", ""),
                            translation=it.get("translation", "")))
    return out, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--seed", type=int, default=20261013)
    ap.add_argument("--local-url", default="http://127.0.0.1:8090")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    words = pick_words(a.n, a.seed)
    prompt = user_prompt(words)
    result = dict(words=words, prompt=prompt)
    for name, fn in (("gemini", lambda: run_gemini(prompt)), ("local", lambda: run_local(prompt, a.local_url))):
        try:
            res = fn()
            res["items"], res["parse_error"] = parse(res["raw"])
        except Exception as e:
            res = dict(error=str(e))
        result[name] = res
        print(name, {k: v for k, v in res.items() if k in ("seconds", "tokens", "parse_error", "error")},
              "items:", len(res.get("items") or []), flush=True)
    with open(a.out, "w") as f:
        json.dump(result, f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
