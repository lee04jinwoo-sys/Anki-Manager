"""읽기 전용: 영어 노트를 로컬 모델 미세조정용 대화 JSONL로 내보낸다.

요청문은 운영 코드의 build_field_prompt(core/completer.py)와 같고, 시스템 프롬프트는 NOTE_COMPLETOR_SYS_INSTRUCT다.
그래서 학습한 모델을 llm_router 경로로 그대로 붙일 수 있다. Anki에 쓰지 않는다.

품질 필터 (현재 카드 작성 규칙, CLAUDE.md):
- 단어: 뜻에 슬래시 없음, 품사 5종(복합은 쉼표), 설명 2단계 공식(의미 문장 + '자주 쓰이는 표현으로는'), 예문 있음
- 문장: 세 단어 이상, 해설에 '~라는 뜻입니다' 같은 메타 설명 없음, A/B 플레이스홀더 없음
- 문법: 필드가 다 있고 보기 네 개(정답 포함)가 서로 다름
필터를 통과한 카드 중 같은 단어/문장(HTML·대소문자 무시)이 여러 번 나오면 처음(오래된) 것만 쓴다.

분할: note id 해시로 test 4%, val 4%, 나머지 train. 다시 돌려도 같은 노트는 같은 쪽에 간다.
출력(data/sft/)에는 단어장 내용이 들어 있어 git에서 제외한다.

실행: .venv/bin/python -m scripts.export_sft_dataset --out data/sft
"""
import argparse
import collections
import hashlib
import html
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, ".")
from config import NOTE_COMPLETOR_SYS_INSTRUCT  # noqa: E402
from core.completer import build_field_prompt  # noqa: E402

ENGLISH_DECK_QUERY = '"deck:1. Language::1.1. English"'
VALID_POS = {"n", "v", "adj", "adv", "idiom"}
TEST_PCT, VAL_PCT = 4, 4

_SOUND = re.compile(r"\[sound:[^\]]*\]")
_TAG = re.compile(r"<[^>]+>")
_SPACE = re.compile(r"\s+")
_EXPLAIN_MEANING = re.compile(r"(은|는) '.+?'(이)?라는 (의미|뜻)")
# 번역 끝에 붙는 메타 설명만 잡는다 ('그가 떠난다는 뜻이야' 같은 정상 번역은 통과)
_META = re.compile(r"는 (뜻|의미)입니다\.?$")
_PLACEHOLDER = re.compile(r"\b[ABC]\b(?!\.)|V-ing")


def clean_field(value):
    text = _SOUND.sub(" ", value or "")
    text = _TAG.sub(" ", text.replace("<br>", " ").replace("<br/>", " "))
    text = html.unescape(text).replace("\xa0", " ")
    return _SPACE.sub(" ", text).strip()


def note_fields(note):
    return {k: clean_field(v.get("value", "")) for k, v in note.get("fields", {}).items()}


def _missing(fields, names):
    return any(not fields.get(n) for n in names)


def vocab_quality(f):
    if _missing(f, ["단어", "뜻", "품사", "예문", "설명"]):
        return False, "missing_field"
    if "/" in f["뜻"]:
        return False, "slash_in_meaning"
    if not {p.strip() for p in f["품사"].split(",")} <= VALID_POS:
        return False, "bad_pos"
    if not (_EXPLAIN_MEANING.search(f["설명"]) and "자주 쓰이는 표현으로는" in f["설명"]):
        return False, "explain_format"
    return True, "ok"


def sentence_quality(f):
    if _missing(f, ["문장", "해설"]):
        return False, "missing_field"
    if len(f["문장"].split()) < 3:
        return False, "too_short"
    if _PLACEHOLDER.search(f["문장"]):
        return False, "placeholder"
    if _META.search(f["해설"]):
        return False, "meta_translation"
    return True, "ok"


def grammar_quality(f):
    names = ["문장", "해설", "설명", "정답", "보기1", "보기2", "보기3"]
    if _missing(f, names):
        return False, "missing_field"
    choices = [f[n].lower() for n in ("정답", "보기1", "보기2", "보기3")]
    if len(set(choices)) < 4:
        return False, "duplicate_choices"
    return True, "ok"


def _bucket(note_id, salt=""):
    return int(hashlib.sha1(f"{salt}{note_id}".encode()).hexdigest(), 16) % 100


def split_for(note_id):
    b = _bucket(note_id)
    if b < TEST_PCT:
        return "test"
    if b < TEST_PCT + VAL_PCT:
        return "val"
    return "train"


TASKS = {
    "English Vocabulary": {"quality": vocab_quality, "main": "단어"},
    "English Sentence": {"quality": sentence_quality, "main": "문장"},
    "English Grammar": {"quality": grammar_quality, "main": "문장"},
}


def _current_and_missing(model, f, note_id):
    """운영에서 보강을 요청할 때와 같은 모양: 사용자가 넣은 필드는 current, 채울 필드는 missing."""
    if model == "English Vocabulary":
        # 단어만 넣는 경우와 단어+뜻을 넣는 경우를 반씩 섞는다
        if _bucket(note_id, salt="variant:") < 50:
            return {"단어": f["단어"]}, ["뜻", "품사", "예문", "설명"]
        return {"단어": f["단어"], "뜻": f["뜻"]}, ["품사", "예문", "설명"]
    if model == "English Sentence":
        return {"문장": f["문장"]}, ["해설"]
    return {"문장": f["문장"], "정답": f["정답"]}, ["해설", "설명", "보기1", "보기2", "보기3"]


def build_example(note, reason_out=None):
    model = note.get("modelName")
    task = TASKS.get(model)
    if task is None:
        return None
    f = note_fields(note)
    ok, reason = task["quality"](f)
    if reason_out is not None:
        reason_out.append(reason)
    if not ok:
        return None
    note_id = note["noteId"]
    current, missing = _current_and_missing(model, f, note_id)
    answer = {k: f[k] for k in missing}
    return {
        "messages": [
            {"role": "system", "content": NOTE_COMPLETOR_SYS_INSTRUCT},
            {"role": "user", "content": build_field_prompt(model, f[task["main"]], current, missing)},
            {"role": "assistant", "content": json.dumps(answer, ensure_ascii=False)},
        ],
        "meta": {"note_id": note_id, "model": model, "split": split_for(note_id),
                 "current": current, "missing": missing},
    }


def export_examples(notes):
    stats = collections.defaultdict(collections.Counter)
    seen = set()
    examples = []
    for note in sorted(notes, key=lambda n: n["noteId"]):
        model = note.get("modelName")
        task = TASKS.get(model)
        if task is None:
            continue
        reasons = []
        example = build_example(note, reasons)
        if example is None:
            stats[model][reasons[0]] += 1
            continue
        # 품질을 통과한 것끼리만 중복을 본다 (앞의 불량 카드가 뒤의 좋은 카드를 막지 않게)
        key = (model, note_fields(note)[task["main"]].lower())
        if key in seen:
            stats[model]["duplicate"] += 1
            continue
        seen.add(key)
        stats[model]["ok"] += 1
        examples.append(example)
    return examples, {m: dict(c) for m, c in stats.items()}


def fetch_notes():
    from integrations.anki_connect import AnkiConnector
    ids = AnkiConnector.find_notes(ENGLISH_DECK_QUERY)
    notes = []
    for i in range(0, len(ids), 2000):
        notes += AnkiConnector.get_notes_info(ids[i:i + 2000])
    return notes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/sft")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    notes = fetch_notes()
    examples, stats = export_examples(notes)
    by_split = collections.defaultdict(list)
    for e in examples:
        by_split[e["meta"]["split"]].append(e)
    for split, rows in by_split.items():
        with open(out / f"{split}.jsonl", "w", encoding="utf-8") as fh:
            for row in rows:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")

    counts = {s: dict(collections.Counter(e["meta"]["model"] for e in rows)) for s, rows in by_split.items()}
    summary = {"notes_read": len(notes), "filter": stats, "examples": counts}
    (out / "stats.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
