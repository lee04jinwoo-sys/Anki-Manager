"""speaking.question_bank 단위 테스트: 72개 Daily 질문 은행 무결성."""
from speaking.question_bank import DAILY_QUESTIONS, get_question_by_id


def test_daily_questions_has_72_unique_prompts_across_categories():
    assert len(DAILY_QUESTIONS) >= 60
    assert len(DAILY_QUESTIONS) == 72

    ids = [q.id for q in DAILY_QUESTIONS]
    prompts = [q.prompt.strip().lower() for q in DAILY_QUESTIONS]
    assert len(set(ids)) == len(DAILY_QUESTIONS)
    assert len(set(prompts)) == len(DAILY_QUESTIONS)

    categories = {q.category for q in DAILY_QUESTIONS}
    assert len(categories) == 8

    for q in DAILY_QUESTIONS:
        assert q.id.startswith("daily_")
        assert q.category.strip()
        assert q.title.strip()
        assert q.prompt.strip()
        assert len(q.bullets) >= 2


def test_get_question_by_id_lookup():
    first = DAILY_QUESTIONS[0]
    assert get_question_by_id(first.id) == first
    assert get_question_by_id("nonexistent_999") is None
