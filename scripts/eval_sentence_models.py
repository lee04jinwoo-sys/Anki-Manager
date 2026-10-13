"""읽기 전용 평가: 미연결 단어 N개로 Gemini Flash-Lite와 로컬 llama-server의 예문 생성을 비교한다.

compare_local_llm.py보다 크게: 20개씩 여러 배치, 자동 검사, 블라인드 판정용 파일.
Anki·links.db에 쓰지 않는다 (links.db는 읽기 전용 URI로 연다).

자동 검사 (단어마다, 생산 코드와 같은 규칙):
- 짝: BatchSentenceGenerator와 같은 방식(정확 일치, 없으면 부분 일치)으로 결과를 단어에 붙인다
- 포함: PatternMatcher.build_regex(단어)가 문장에 걸리는지 (= 등록하면 그 단어에 링크되는지)
- 기호: 문장에 V-ing / V / 단독 대문자 A·B·C 플레이스홀더가 남았는지
- 번역: 한글이 있는지

실행 (서버, ~/anki-manager에서, llama-server가 --local-url에 떠 있어야 함):
    .venv/bin/python scripts/eval_sentence_models.py --n 100 --exclude-from ~/llm/compare.json --out ~/llm/eval100
"""
import argparse
import json
import random
import re
import sqlite3
import sys
import time
from pathlib import Path

sys.path.insert(0, ".")
from core.link_manager import PatternMatcher  # noqa: E402
from scripts.compare_local_llm import parse, run_gemini, run_local, user_prompt  # noqa: E402

BATCH = 20
HANGUL = re.compile(r"[가-힣]")
# 문장 첫 단어의 관사 A는 허용, 문장 중간의 단독 A/B/C와 V-ing·V는 기호 노출로 본다
PLACEHOLDER = re.compile(r"(?<!^)(?<![.!?]\s)\b[ABC]\b(?!\.)|\bV-ing\b|\bV\b")


def pick_words(n, seed, exclude):
    con = sqlite3.connect("file:data/links.db?mode=ro", uri=True)
    rows = con.execute(
        "SELECT note_id, word, meaning FROM vocab_cache WHERE link_count = 0 ORDER BY note_id").fetchall()
    rows = [r for r in rows if r[0] not in exclude]
    return [dict(note_id=r[0], word=r[1], meaning=r[2] or "") for r in random.Random(seed).sample(rows, n)]


def match_items(words, items):
    """BatchSentenceGenerator.generate_and_add_sentences와 같은 짝짓기. {단어 소문자: item}"""
    vocab_map = {w["word"].strip().lower(): w for w in words}
    out = {}
    for it in items or []:
        norm = str(it.get("word", "")).strip().lower()
        v = vocab_map.get(norm)
        if not v:
            v = next((cand for k, cand in vocab_map.items() if k in norm or norm in k), None)
        if v and v["word"].lower() not in out:
            out[v["word"].lower()] = it
    return out


def check(word, item):
    if not item:
        return dict(paired=False)
    sent, trans = str(item.get("sentence", "")), str(item.get("translation", ""))
    rx = PatternMatcher.build_regex(word)
    return dict(
        paired=True,
        contains=None if rx is None else bool(rx.search(sent)),
        placeholder=bool(PLACEHOLDER.search(sent)),
        korean=bool(HANGUL.search(trans)),
    )


def summarize(rows, name):
    n = len(rows)
    c = [r[name] for r in rows]
    judged = [x for x in c if x.get("paired") and x.get("contains") is not None]
    return dict(
        words=n,
        paired=sum(x.get("paired", False) for x in c),
        contains=f"{sum(x['contains'] for x in judged)}/{len(judged)}",
        no_regex=sum(1 for x in c if x.get("paired") and x.get("contains") is None),
        placeholder=sum(x.get("placeholder", False) for x in c),
        korean=sum(x.get("korean", False) for x in c),
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--seed", type=int, default=20261014)
    ap.add_argument("--exclude-from", help="이미 시험한 단어가 든 compare.json")
    ap.add_argument("--local-url", default="http://127.0.0.1:8090")
    ap.add_argument("--out", required=True, help="결과 폴더")
    a = ap.parse_args()

    exclude = set()
    if a.exclude_from:
        exclude = {w["note_id"] for w in json.load(open(a.exclude_from))["words"]}
    words = pick_words(a.n, a.seed, exclude)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)

    batches = []
    for b in range(0, len(words), BATCH):
        chunk = words[b:b + BATCH]
        prompt = user_prompt(chunk)
        batch = dict(words=chunk)
        for name, fn in (("gemini", lambda: run_gemini(prompt)), ("local", lambda: run_local(prompt, a.local_url))):
            try:
                res = fn()
                res["items"], res["parse_error"] = parse(res["raw"])
            except Exception as e:
                res = dict(error=str(e), items=[])
            batch[name] = res
            print(f"batch {b // BATCH + 1} {name}", {k: res.get(k) for k in ("seconds", "tokens", "parse_error", "error")},
                  "items:", len(res.get("items") or []), flush=True)
        batches.append(batch)
        (out / "raw.json").write_text(json.dumps(batches, ensure_ascii=False, indent=1))

    rows = []
    for batch in batches:
        g = match_items(batch["words"], batch["gemini"].get("items"))
        l = match_items(batch["words"], batch["local"].get("items"))
        for w in batch["words"]:
            k = w["word"].lower()
            rows.append(dict(word=w["word"], meaning=w["meaning"], gemini_item=g.get(k), local_item=l.get(k),
                             gemini=check(w["word"], g.get(k)), local=check(w["word"], l.get(k))))

    summary = dict(
        gemini=summarize(rows, "gemini"), local=summarize(rows, "local"),
        seconds=dict(gemini=round(sum(b["gemini"].get("seconds", 0) for b in batches), 1),
                     local=round(sum(b["local"].get("seconds", 0) for b in batches), 1)),
        tokens_gemini=dict(prompt=sum(b["gemini"].get("tokens", {}).get("prompt", 0) for b in batches),
                           output=sum(b["gemini"].get("tokens", {}).get("output", 0) for b in batches)),
    )
    (out / "rows.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1))
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1))
    print(json.dumps(summary, ensure_ascii=False, indent=1))

    # 블라인드 판정용: 둘 다 짝이 있는 단어만, A/B 순서를 무작위로. 정답표는 따로 저장
    rnd = random.Random(a.seed + 1)
    blind, key = [], {}
    for i, r in enumerate(rows):
        if not (r["gemini_item"] and r["local_item"]):
            continue
        pair = [("gemini", r["gemini_item"]), ("local", r["local_item"])]
        rnd.shuffle(pair)
        blind.append(dict(id=i, word=r["word"], meaning=r["meaning"][:40],
                          A=dict(sentence=pair[0][1]["sentence"], translation=pair[0][1]["translation"]),
                          B=dict(sentence=pair[1][1]["sentence"], translation=pair[1][1]["translation"])))
        key[i] = dict(A=pair[0][0], B=pair[1][0])
    (out / "blind.json").write_text(json.dumps(blind, ensure_ascii=False, indent=1))
    (out / "blind_key.json").write_text(json.dumps(key, indent=1))


if __name__ == "__main__":
    main()
