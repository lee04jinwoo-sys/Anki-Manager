"""Compare Gemini models on vocabulary enrichment (NoteCompleter.enrich_vocab), read-only.

- Picks vocabulary words from the collection with findNotes/notesInfo only (no writes).
- Runs enrich_vocab with only the word given, once per model.
- Checks the output against the current card rules (config.py NOTE_COMPLETOR_SYS_INSTRUCT).
- Writes everything to data/eval/ (git-ignored).

    .venv/bin/python scripts/compare_enrich_models.py --anki http://127.0.0.1:18765 \
        --models gemini-3.5-flash-lite gemini-3.8-flash --n 20
"""
import argparse
import json
import random
import re
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.completer import NoteCompleter  # noqa: E402

READ_ONLY_ACTIONS = {"findNotes", "notesInfo", "version"}
ALLOWED_POS = {"n", "v", "adj", "adv", "idiom"}
PLACEHOLDER = re.compile(r"\b(A|B|C|V|V-ing|sb|sth|someone|something)\b")
HANGUL = re.compile(r"[가-힣]")


def anki(url, action, **params):
    assert action in READ_ONLY_ACTIONS, f"refusing non-read action {action}"
    s = requests.Session()
    s.trust_env = False
    r = s.post(url, json={"action": action, "version": 6, "params": params}, timeout=30).json()
    if r.get("error"):
        raise RuntimeError(r["error"])
    return r["result"]


def strip_html(t):
    return re.sub(r"<[^>]+>", "", t or "").replace("&nbsp;", " ").strip()


def pick_words(url, n, seed):
    ids = anki(url, "findNotes", query='note:"English Vocabulary"')
    rng = random.Random(seed)
    rng.shuffle(ids)
    single, multi = [], []
    for chunk_start in range(0, len(ids), 200):
        for note in anki(url, "notesInfo", notes=ids[chunk_start:chunk_start + 200]):
            word = strip_html(note["fields"].get("단어", {}).get("value", ""))
            if not word or len(word) > 40:
                continue
            (multi if " " in word else single).append({
                "단어": word,
                "existing": {k: strip_html(v["value"]) for k, v in note["fields"].items() if k in ("뜻", "품사", "예문", "설명")},
            })
        if len(single) >= n // 2 and len(multi) >= n - n // 2:
            break
    return single[: n // 2] + multi[: n - n // 2]


def check(item):
    """Rule violations for one enriched item."""
    issues = []
    meaning = str(item.get("뜻", ""))
    pos = str(item.get("품사", ""))
    example = str(item.get("예문", ""))
    expl = str(item.get("설명", ""))
    if not meaning:
        issues.append("뜻 없음")
    if "/" in meaning:
        issues.append("뜻에 슬래시")
    pos_parts = {p.strip() for p in pos.split(",") if p.strip()}
    if not pos_parts or not pos_parts <= ALLOWED_POS:
        issues.append(f"품사 비표준({pos})")
    if not example:
        issues.append("예문 없음")
    if PLACEHOLDER.search(example):
        issues.append("예문에 플레이스홀더")
    if HANGUL.search(example):
        issues.append("예문에 한글")
    if "이라는 의미로" not in expl and "라는 의미로" not in expl:
        issues.append("설명 ①형식 아님")
    if "자주 쓰이는 표현" not in expl:
        issues.append("설명 ②(콜로케이션) 없음")
    if "유의어" in expl or "비슷하지만" in expl:
        issues.append("설명에 유의어 비교")
    if str(item.get("유의어", "")).strip():
        issues.append("유의어 채움")
    return issues


def run_model(model, words):
    completer = NoteCompleter()
    completer.model_id = model
    started = time.monotonic()
    out = completer.enrich_vocab([{"단어": w["단어"]} for w in words])
    seconds = round(time.monotonic() - started, 1)
    by_word = {str(o.get("단어", "")).strip().lower(): o for o in out if isinstance(o, dict)}
    rows = []
    for w in words:
        o = by_word.get(w["단어"].lower())
        rows.append({"단어": w["단어"], "output": o, "issues": check(o) if o else ["응답 없음"]})
    return {"model": model, "seconds": seconds, "rows": rows}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--anki", default="http://127.0.0.1:18765")
    ap.add_argument("--models", nargs="+", default=["gemini-3.5-flash-lite", "gemini-3.8-flash"])
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--seed", type=int, default=20261012)
    args = ap.parse_args()

    words = pick_words(args.anki, args.n, args.seed)
    print(f"{len(words)} words: {[w['단어'] for w in words]}")
    results = [run_model(m, words) for m in args.models]

    for r in results:
        bad = [row for row in r["rows"] if row["issues"]]
        print(f"\n=== {r['model']}  {r['seconds']}s  rule-clean {len(words) - len(bad)}/{len(words)}")
        counts = {}
        for row in r["rows"]:
            for i in row["issues"]:
                counts[i] = counts.get(i, 0) + 1
        for k, v in sorted(counts.items(), key=lambda x: -x[1]):
            print(f"   {k}: {v}")

    out_dir = ROOT / "data" / "eval"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"enrich-compare-{datetime.now():%Y%m%d-%H%M%S}.json"
    path.write_text(json.dumps({"words": words, "results": results}, ensure_ascii=False, indent=2))
    print(f"\nfull results: {path}")


if __name__ == "__main__":
    main()
