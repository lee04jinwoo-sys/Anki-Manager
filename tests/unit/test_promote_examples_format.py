"""승격 시 예문 필드 형식: 영어 예문만 ' ||| '로 구분 (번역·번호·HTML 없음).

예전 형식("1. ...<br><span>번역</span><br><br>2. ...")은 빈칸 엔진에서 한 문장으로 취급되어
카드 앞면에 번역과 2번 예문이 그대로 노출됐다.
"""
from backend.services.corpus_service import format_promote_examples


def test_examples_are_plain_english_joined():
    out = format_promote_examples("The cat was lurking behind the curtain.", "A hidden agenda lurks behind his offers.")
    assert out == "The cat was lurking behind the curtain. ||| A hidden agenda lurks behind his offers."


def test_blank_second_example_is_skipped_and_whitespace_trimmed():
    assert format_promote_examples("  One sentence.  ", "   ") == "One sentence."
