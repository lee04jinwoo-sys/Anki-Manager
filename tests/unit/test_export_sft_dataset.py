import json

from config import NOTE_COMPLETOR_SYS_INSTRUCT
from core.completer import build_field_prompt
from scripts import export_sft_dataset as ex

def vocab_note(note_id=1, **over):
    fields = {"단어": "locate", "뜻": "위치를 찾아내다, ~에 두다", "품사": "v", "유의어": "",
              "예문": "Rescue planes are trying to locate the missing people.", "사진": "",
              "소리": "[sound:google-abc.mp3]"}
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
              "정답": "has been discussing",
              "보기1": "discussed", "보기2": "discusses", "보기3": "is discussing", "소리": ""}
    fields.update(over)
    return {"noteId": note_id, "modelName": "English Grammar",
            "fields": {k: {"value": v} for k, v in fields.items()}}


def test_clean_field_strips_sound_html_and_keeps_example_separator():
    raw = "<b>One</b>&nbsp;example. ||| Two&#x27;s  example. [sound:a.mp3]"
    assert ex.clean_field(raw) == "One example. ||| Two's example."


def test_vocab_quality_accepts_rule_conforming_card():
    assert ex.vocab_quality(ex.note_fields(vocab_note())) == (True, "ok")


def test_vocab_example_carries_normalized_meaning_and_pos():
    example = ex.build_example(vocab_note(note_id=11, 뜻="찾다/두다", 품사="v phr"))
    answer = json.loads(example["messages"][2]["content"])
    current = example["meta"]["current"]
    assert answer.get("뜻", current.get("뜻")) == "찾다, 두다"
    assert answer["품사"] == "idiom"


def vocab_fields(**over):
    return ex.normalize_fields("English Vocabulary", ex.note_fields(vocab_note(**over)))


def test_normalize_turns_slash_in_meaning_into_comma():
    assert vocab_fields(뜻="제시하다/설명하다")["뜻"] == "제시하다, 설명하다"
    assert vocab_fields(뜻="운동하다 / 잘 풀리다")["뜻"] == "운동하다, 잘 풀리다"


def test_normalize_maps_phrase_pos_to_idiom():
    assert vocab_fields(품사="v phr")["품사"] == "idiom"
    assert vocab_fields(품사="n phr")["품사"] == "idiom"


def test_vocab_quality_accepts_preposition_and_compound_pos():
    assert ex.vocab_quality(vocab_fields(품사="prep"))[0]
    assert ex.vocab_quality(vocab_fields(품사="n, v"))[0]


def test_vocab_quality_rejects_unknown_pos():
    ok, reason = ex.vocab_quality(vocab_fields(품사="det"))
    assert not ok and reason == "bad_pos"


def test_vocab_quality_rejects_missing_example():
    ok, reason = ex.vocab_quality(vocab_fields(예문=""))
    assert not ok and reason == "missing_field"


def test_sentence_quality_rejects_meta_translation():
    ok, reason = ex.sentence_quality(ex.note_fields(sentence_note(해설="그는 건강했다는 뜻입니다.")))
    assert not ok and reason == "meta_translation"


def test_sentence_quality_keeps_translation_of_a_sentence_about_meaning():
    f = ex.note_fields(sentence_note(문장="Respect literally means to look again.",
                                     해설="존중(Respect)은 문자 그대로 '다시 본다'는 의미입니다."))
    assert ex.sentence_quality(f)[0]


def test_sentence_quality_rejects_leftover_placeholder():
    ok, reason = ex.sentence_quality(ex.note_fields(sentence_note(문장="I want to prevent A from leaving.")))
    assert not ok and reason == "placeholder"


def test_sentence_quality_keeps_article_a_at_sentence_start():
    for s in ["A bird flew in through the window.", "Watch out! A car’s coming.", "A piece of cake."]:
        assert ex.sentence_quality(ex.note_fields(sentence_note(문장=s)))[0], s


def test_sentence_quality_keeps_two_word_expressions():
    assert ex.sentence_quality(ex.note_fields(sentence_note(문장="Take care.")))[0]


def test_sentence_quality_rejects_single_word():
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
    assert ("뜻", "품사", "예문") in variants
    assert ("품사", "예문") in variants


def test_sentence_example_asks_only_for_translation():
    example = ex.build_example(sentence_note())
    assert json.loads(example["messages"][2]["content"]) == {"해설": "그는 건강했었는데."}


def test_grammar_example_gives_sentence_and_answer_and_asks_for_rest():
    example = ex.build_example(grammar_note())
    assert example["meta"]["current"] == {"문장": "The team has been discussing it since Monday.",
                                          "정답": "has been discussing"}
    assert set(json.loads(example["messages"][2]["content"])) == {"해설", "보기1", "보기2", "보기3"}


def test_build_example_returns_none_for_rejected_or_unknown_notes():
    assert ex.build_example(vocab_note(예문="")) is None
    assert ex.build_example({"noteId": 9, "modelName": "Basic", "fields": {}}) is None


def test_export_drops_duplicate_main_field_and_counts_reasons():
    notes = [vocab_note(note_id=1), vocab_note(note_id=2, 단어="<b>Locate</b>"), vocab_note(note_id=3, 예문="")]
    examples, stats = ex.export_examples(notes)
    assert [e["meta"]["note_id"] for e in examples] == [1]
    assert stats["English Vocabulary"]["duplicate"] == 1
    assert stats["English Vocabulary"]["missing_field"] == 1
    assert stats["English Vocabulary"]["ok"] == 1


def test_export_lists_rejected_note_ids_for_manual_fix():
    examples, stats = ex.export_examples([grammar_note(note_id=7, 보기3="has been discussing")])
    assert examples == []
    assert stats["rejected"] == [{"note_id": 7, "model": "English Grammar", "reason": "duplicate_choices"}]
