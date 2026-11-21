from speaking.coach import SpeakingCoach
from speaking.models import SpeakingCard, SpeakingMetrics


def _coach(payload):
    return SpeakingCoach(generate_json_fn=lambda sys_p, user_p, temp: (payload, "fake"))


def test_candidates_are_capped_per_kind_and_corrections_uncapped():
    payload = {
        "score": 7,
        "summary": "s",
        "corrections": [f"a{i} -> b{i} (이유)" for i in range(8)],
        "native_model": "whole answer",
        "card_candidates": (
            [{"kind": "sentence", "text": f"sentence {i}", "translation": "t"} for i in range(8)]
            + [{"kind": "vocab", "text": f"word {i}", "translation": "m"} for i in range(8)]
        ),
    }
    card = SpeakingCard(card_id=1, note_id=1, topic_id="d", prompt_text="Q?")
    ev = _coach(payload).evaluate_card(card, "transcript", SpeakingMetrics())

    assert len(ev.corrections) == 8
    kinds = [c.kind for c in ev.card_candidates]
    assert kinds.count("sentence") == 5
    assert kinds.count("vocab") == 5
