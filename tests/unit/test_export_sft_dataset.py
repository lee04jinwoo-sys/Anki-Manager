import json

from config import NOTE_COMPLETOR_SYS_INSTRUCT
from core.completer import build_field_prompt
from scripts import export_sft_dataset as ex

GOOD_EXPLAIN = ("locate는 '위치를 찾아내다'라는 의미로, 정확한 위치를 파악하는 것을 나타냅니다. "
                "자주 쓰이는 표현으로는 'locate the source(원인을 찾아내다)' 등이 있습니다.")


def vocab_note(note_id=1, **over):
    fields = {"단어": "locate", "뜻": "위치를 찾아내다, ~에 두다", "품사": "v", "유의어": "",
              "예문": "Rescue planes are trying to locate the missing people.", "사진": "",
              "설명": GOOD_EXPLAIN, "소리": "[sound:google-abc.mp3]"}
    fields.update(over)
    return {"noteId": note_id, "modelName": "English Vocabulary",
            "fields": {k: {"value": v} for k, v in fields.items()}}


def sentence_note(note_id=2, **over):
    fields = {"문장": "He used to be healthy.", "해설": "그는 건강했었는데.", "소리": "[sound:x.mp3]"}
    fields.update(over)
    return {"noteId": note_id, "modelName": "English Sentence",
            "fields": {k: {"value": v} for k, v in fields.items()}}


def grammar_note(note_id=3, **over):
    fields = {"문장": "The team has been discussing it since Monday.", "해설": "팀은 월요일부터 그것을 논의해 왔다.",
              "설명": "'since + 과거 시점'이 있어 현재완료 진행형이 맞습니다.", "정답": "has been discussing",
              "보기1": "discussed", "보기2": "discusses", "보기3": "is discussing", "소리": ""}
    fields.update(over)
    return {"noteId": note_id, "modelName": "English Grammar",
            "fields": {k: {"value": v} for k, v in fields.items()}}


def test_clean_field_strips_sound_html_and_keeps_example_separator():
    raw = "<b>One</b>&nbsp;example. ||| Two&#x27;s  example. [sound:a.mp3]"
    assert ex.clean_field(raw) == "One example. ||| Two's example."


def test_vocab_quality_accepts_rule_conforming_card():
    assert ex.vocab_quality(ex.note_fields(vocab_note())) == (True, "ok")


def test_vocab_quality_rejects_slash_in_meaning():
    ok, reason = ex.vocab_quality(ex.note_fields(vocab_note(뜻="찾다/두다")))
    assert not ok and reason == "slash_in_meaning"


def test_vocab_quality_rejects_nonstandard_pos():
    ok, reason = ex.vocab_quality(ex.note_fields(vocab_note(품사="v phr")))
    assert not ok and reason == "bad_pos"


def test_vocab_quality_accepts_compound_pos():
    assert ex.vocab_quality(ex.note_fields(vocab_note(품사="n, v")))[0]


def test_vocab_quality_rejects_explanation_without_collocation_step():
    ok, reason = ex.vocab_quality(ex.note_fields(vocab_note(설명="locate는 '찾다'라는 의미로, 위치를 나타냅니다.")))
    assert not ok and reason == "explain_format"


def test_vocab_quality_rejects_missing_example():
    ok, reason = ex.vocab_quality(ex.note_fields(vocab_note(예문="")))
    assert not ok and reason == "missing_field"


def test_sentence_quality_rejects_meta_translation():
    ok, reason = ex.sentence_quality(ex.note_fields(sentence_note(해설="그는 건강했다는 뜻입니다.")))
    assert not ok and reason == "meta_translation"


def test_sentence_quality_rejects_leftover_placeholder():
    ok, reason = ex.sentence_quality(ex.note_fields(sentence_note(문장="I want to prevent A from leaving.")))
    assert not ok and reason == "placeholder"


def test_sentence_quality_rejects_fragment():
    ok, reason = ex.sentence_quality(ex.note_fields(sentence_note(문장="Healthy.")))
    assert not ok and reason == "too_short"


def test_grammar_quality_rejects_duplicate_choices():
    ok, reason = ex.grammar_quality(ex.note_fields(grammar_note(보기3="has been discussing")))
    assert not ok and reason == "duplicate_choices"


def test_grammar_quality_accepts_complete_card():
    assert ex.grammar_quality(ex.note_fields(grammar_note())) == (True, "ok")


def test_split_is_deterministic_and_roughly_proportional():
    splits = [ex.split_for(i) for i in range(20000)]
    assert splits == [ex.split_for(i) for i in range(20000)]
    test_share = splits.count("test") / len(splits)
    val_share = splits.count("val") / len(splits)
    assert 0.03 < test_share < 0.05
    assert 0.03 < val_share < 0.05


def test_vocab_example_uses_production_prompt_and_returns_only_missing_fields():
    example = ex.build_example(vocab_note(note_id=10))
    system, user, assistant = (m["content"] for m in example["messages"])
    meta = example["meta"]
    assert system == NOTE_COMPLETOR_SYS_INSTRUCT
    assert user == build_field_prompt("English Vocabulary", "locate", meta["current"], meta["missing"])
    answer = json.loads(assistant)
    assert set(answer) == set(meta["missing"])
    assert "단어" in meta["current"]
    assert "소리" not in answer and "유의어" not in answer


def test_vocab_examples_alternate_between_word_only_and_word_with_meaning():
    variants = {tuple(ex.build_example(vocab_note(note_id=i))["meta"]["missing"]) for i in range(40)}
    assert ("뜻", "품사", "예문", "설명") in variants
    assert ("품사", "예문", "설명") in variants


def test_sentence_example_asks_only_for_translation():
    example = ex.build_example(sentence_note())
    assert json.loads(example["messages"][2]["content"]) == {"해설": "그는 건강했었는데."}


def test_grammar_example_gives_sentence_and_answer_and_asks_for_rest():
    example = ex.build_example(grammar_note())
    assert example["meta"]["current"] == {"문장": "The team has been discussing it since Monday.",
                                          "정답": "has been discussing"}
    assert set(json.loads(example["messages"][2]["content"])) == {"해설", "설명", "보기1", "보기2", "보기3"}


def test_build_example_returns_none_for_rejected_or_unknown_notes():
    assert ex.build_example(vocab_note(뜻="a/b")) is None
    assert ex.build_example({"noteId": 9, "modelName": "Basic", "fields": {}}) is None


def test_export_drops_duplicate_main_field_and_counts_reasons():
    notes = [vocab_note(note_id=1), vocab_note(note_id=2, 단어="<b>Locate</b>"), vocab_note(note_id=3, 뜻="a/b")]
    examples, stats = ex.export_examples(notes)
    assert [e["meta"]["note_id"] for e in examples] == [1]
    assert stats["English Vocabulary"]["duplicate"] == 1
    assert stats["English Vocabulary"]["slash_in_meaning"] == 1
    assert stats["English Vocabulary"]["ok"] == 1
