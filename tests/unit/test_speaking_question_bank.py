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
        assert q.prompt.strip().endswith(("?", "."))
        assert "\n" not in q.prompt


def test_everyday_categories_come_before_tech_and_presentations():
    cats = [q.category for q in DAILY_QUESTIONS]
    first_later = min(i for i, c in enumerate(cats) if c in ("Opinions & Tech", "Projects & Presentations"))
    assert all(c not in ("Opinions & Tech", "Projects & Presentations") for c in cats[:first_later])
    assert first_later == 54


def test_get_question_by_id_lookup():
    first = DAILY_QUESTIONS[0]
    assert get_question_by_id(first.id) == first
    assert get_question_by_id("nonexistent_999") is None
