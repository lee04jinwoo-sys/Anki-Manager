"""읽기 전용: 영어 노트를 로컬 모델 미세조정용 대화 JSONL로 내보낸다.

요청문은 운영 코드의 build_field_prompt(core/completer.py)와 같고, 시스템 프롬프트는 NOTE_COMPLETOR_SYS_INSTRUCT다.
그래서 학습한 모델을 llm_router 경로로 그대로 붙일 수 있다. Anki에 쓰지 않는다.

최대한 많은 카드를 쓰되, 고칠 수 있는 것은 고쳐서 넣는다 (2026-11-22 전체 거절 사유 검토 후):
- 단어: 뜻의 슬래시는 쉼표로 바꾸고, 'v phr'·'n phr' 같은 구 품사는 규칙대로 idiom으로 바꾼다.
  품사는 규칙의 5종에 실제 카드에 쓰인 prep을 더해 받는다. 설명은 문구가 공식과 달라도 받는다
  (공식을 그대로 따른 카드는 704개뿐이고 나머지도 내용은 같은 수준이다).
- 문장: 두 단어 이상('Take care.'), 해설 끝의 메타 설명('~는 뜻입니다') 없음(원문이 mean을 다루면 예외),
  문장 중간에 남은 A/B/C·V-ing 플레이스홀더 없음(문장 맨 앞의 관사 A는 통과)
- 문법: 필드가 다 있고 보기 네 개(정답 포함)가 서로 다름. 걸린 노트 id는 stats.json에 남겨 Anki에서 고친다.
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
VALID_POS = {"n", "v", "adj", "adv", "idiom", "prep"}
PHRASE_POS = {"v phr", "n phr", "phrase", "collocation"}  # 규칙상 모두 idiom
TEST_PCT, VAL_PCT = 4, 4

_SOUND = re.compile(r"\[sound:[^\]]*\]")
_TAG = re.compile(r"<[^>]+>")
_SPACE = re.compile(r"\s+")
_SLASH = re.compile(r"\s*/\s*")
# 번역 끝에 붙는 메타 설명만 잡는다 ('그가 떠난다는 뜻이야' 같은 정상 번역은 통과)
_META = re.compile(r"는 (뜻|의미)입니다\.?$")
_LETTER_TOKEN = re.compile(r"(?<![&\w])([ABC])\b(?!\.)")
_SENTENCE_START = re.compile(r"[.!?…][\"'”’)]?\s+$")
_NAMED_LETTER = re.compile(r"(Plan|Vitamin|vitamin|grade|Grade|type|Type|Option|option|class|Class|part|Part)\s+$")


def clean_field(value):
    text = _SOUND.sub(" ", value or "")
    text = _TAG.sub(" ", text.replace("<br>", " ").replace("<br/>", " "))
    text = html.unescape(text).replace("\xa0", " ")
    return _SPACE.sub(" ", text).strip()


def note_fields(note):
    return {k: clean_field(v.get("value", "")) for k, v in note.get("fields", {}).items()}


def normalize_fields(model, f):
    """규칙 위반 중 기계적으로 고칠 수 있는 것을 고친다 (단어 카드의 뜻 슬래시, 구 품사)."""
    if model != "English Vocabulary":
        return f
    f = dict(f)
    f["뜻"] = _SLASH.sub(", ", f.get("뜻", ""))
    parts = [p.strip() for p in f.get("품사", "").split(",") if p.strip()]
    f["품사"] = ", ".join(dict.fromkeys("idiom" if p in PHRASE_POS else p for p in parts))
    return f


def _missing(fields, names):
    return any(not fields.get(n) for n in names)


def has_placeholder(sentence):
    """문장 중간에 남은 A/B/C·V-ing. 문장 맨 앞의 관사 A, Q&A, Plan B 같은 이름은 제외한다."""
    if "V-ing" in sentence:
        return True
    for m in _LETTER_TOKEN.finditer(sentence):
        before = sentence[:m.start()]
        if m.group(1) == "A" and (not before.strip() or _SENTENCE_START.search(before)):
            continue
        if _NAMED_LETTER.search(before):
            continue
        return True
    return False


def vocab_quality(f):
    if _missing(f, ["단어", "뜻", "품사", "예문"]):
        return False, "missing_field"
    if "/" in f["뜻"]:
        return False, "slash_in_meaning"
    if not {p.strip() for p in f["품사"].split(",")} <= VALID_POS:
        return False, "bad_pos"
    return True, "ok"


def sentence_quality(f):
    if _missing(f, ["문장", "해설"]):
        return False, "missing_field"
    if len(f["문장"].split()) < 2:
        return False, "too_short"
    if has_placeholder(f["문장"]):
        return False, "placeholder"
    if _META.search(f["해설"]) and not re.search(r"\bmean", f["문장"], re.I):
        return False, "meta_translation"
    return True, "ok"


def grammar_quality(f):
    names = ["문장", "해설", "정답", "보기1", "보기2", "보기3"]
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
            return {"단어": f["단어"]}, ["뜻", "품사", "예문"]
        return {"단어": f["단어"], "뜻": f["뜻"]}, ["품사", "예문"]
    if model == "English Sentence":
        return {"문장": f["문장"]}, ["해설"]
    return {"문장": f["문장"], "정답": f["정답"]}, ["해설", "보기1", "보기2", "보기3"]


def build_example(note, reason_out=None):
    model = note.get("modelName")
    task = TASKS.get(model)
    if task is None:
        return None
    f = normalize_fields(model, note_fields(note))
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
    rejected = []
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
            rejected.append({"note_id": note["noteId"], "model": model, "reason": reasons[0]})
            continue
        # 품질을 통과한 것끼리만 중복을 본다 (앞의 불량 카드가 뒤의 좋은 카드를 막지 않게)
        key = (model, note_fields(note)[task["main"]].lower())
        if key in seen:
            stats[model]["duplicate"] += 1
            continue
        seen.add(key)
        stats[model]["ok"] += 1
        examples.append(example)
    summary = {m: dict(c) for m, c in stats.items()}
    summary["rejected"] = rejected
    return examples, summary


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
