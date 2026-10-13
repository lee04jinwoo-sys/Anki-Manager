"""읽기 전용 평가: 로컬 llama-server가 예문 카드의 오류를 알아보는지 잰다 (검수자로 쓸 수 있는지).

데이터: eval_sentence_models.py 결과 폴더의 blind.json, blind_key.json, judgments.json
(judgments.json = Claude가 블라인드로 표시한 '카드로 못 쓸 오류' 14개, 2026-10-13).
문장마다 단어·뜻·영어 문장·한국어 번역을 주고 OK/BAD를 묻는다. 10문장씩 섞어서 한 요청.
Anki에 쓰지 않는다.

통과 기준 (결과를 보기 전에 정함, 2026-10-13):
- 재현율: 표시된 오류 14개 중 7개 이상을 BAD로 잡는다
- 오탐: 나머지 문장 중 BAD로 거는 비율이 10% 이하
둘 다 만족하면 '검수자로 쓸 만함'. 한계: 라벨은 한 명(Claude)이 붙였고 오류 수가 적다.

실행 (서버, ~/anki-manager, llama-server는 --cache-ram 0으로):
    .venv/bin/python scripts/eval_local_checker.py --data ~/llm/eval100 --out ~/llm/eval100/checker.json
"""
import argparse
import json
import random
import time
from pathlib import Path

import requests

CHECK_PROMPT = """You review English flashcards for a Korean learner. Each item has a target word, its Korean meaning, an English example sentence and its Korean translation.
Mark an item BAD only if it has a real problem that would make a bad flashcard:
- the sentence does not use the target word, or uses it in a different meaning than the given Korean meaning
- the English sentence is ungrammatical or unnatural
- the Korean translation is wrong, mistranslates a word, or drops part of the meaning
- the sentence is factually absurd
Small style differences are OK. Return JSON only: {"bad": [{"i": <item number>, "why": "<max 8 words>"}]}. Use {"bad": []} if all are fine."""

BATCH = 10


def load_items(data):
    blind = json.loads((data / "blind.json").read_text())
    key = json.loads((data / "blind_key.json").read_text())
    judg = json.loads((data / "judgments.json").read_text())
    bad = {(int(i), key[i][side]) for side in "AB" for i in judg[f"error_{side}"]}
    items = []
    for x in blind:
        for side in "AB":
            model = key[str(x["id"])][side]
            items.append(dict(pair=x["id"], model=model, word=x["word"], meaning=x["meaning"],
                              sentence=x[side]["sentence"], translation=x[side]["translation"],
                              label_bad=(x["id"], model) in bad))
    return items


def ask(batch, url):
    lines = [f"{n + 1}. word: {it['word']} | meaning: {it['meaning']}\n   sentence: {it['sentence']}\n   translation: {it['translation']}"
             for n, it in enumerate(batch)]
    t = time.time()
    r = requests.post(f"{url}/v1/chat/completions", timeout=1800, json=dict(
        messages=[{"role": "system", "content": CHECK_PROMPT}, {"role": "user", "content": "\n".join(lines)}],
        temperature=0, max_tokens=400, response_format={"type": "json_object"}))
    r.raise_for_status()
    d = r.json()
    raw = d["choices"][0]["message"]["content"]
    flagged = {}
    for b in json.loads(raw).get("bad", []):
        try:
            flagged[int(b["i"])] = str(b.get("why", ""))
        except (KeyError, TypeError, ValueError):
            continue
    return flagged, raw, round(time.time() - t, 1), d.get("usage")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--url", default="http://127.0.0.1:8090")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    items = load_items(Path(a.data).expanduser())
    random.Random(a.seed).shuffle(items)

    for b in range(0, len(items), BATCH):
        batch = items[b:b + BATCH]
        try:
            flagged, raw, sec, usage = ask(batch, a.url)
        except Exception as e:
            flagged, raw, sec, usage = {}, f"ERROR {e}", None, None
            for it in batch:
                it["error"] = True
        for n, it in enumerate(batch):
            it["flag_bad"] = (n + 1) in flagged
            it["why"] = flagged.get(n + 1, "")
        print(f"batch {b // BATCH + 1}: {sec}s usage={usage} flagged={sorted(flagged)}", flush=True)
        Path(a.out).write_text(json.dumps(items, ensure_ascii=False, indent=1))

    ok = [it for it in items if not it.get("error")]
    pos = [it for it in ok if it["label_bad"]]
    neg = [it for it in ok if not it["label_bad"]]
    caught = sum(it["flag_bad"] for it in pos)
    false_flags = sum(it["flag_bad"] for it in neg)
    summary = dict(items=len(items), errors=len(items) - len(ok), labeled_bad=len(pos),
                   recall=f"{caught}/{len(pos)}", false_positive=f"{false_flags}/{len(neg)}",
                   false_positive_rate=round(false_flags / len(neg), 3) if neg else None,
                   passed=caught >= 7 and neg and false_flags / len(neg) <= 0.10)
    print(json.dumps(summary, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
