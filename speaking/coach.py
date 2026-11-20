"""LLM speaking coach built on top of core.llm_router.generate_json."""
from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional, Sequence

from core import llm_router
from speaking.models import (
    CardCandidate,
    CardEvaluation,
    EaseRating,
    SpeakingCard,
    SpeakingMetrics,
)

logger = logging.getLogger("speaking.coach")

_SYSTEM_PROMPT = (
    "You are a concise, objective English speaking coach for a B2-C1 Korean university student "
    "in Toronto working on natural everyday fluency, campus communication, and clear spoken expression. "
    "Respond ONLY with valid JSON matching the requested schema. "
    "Write feedback explanations in crisp Korean without flattery or filler praise."
)


def _score_to_ease(score: float) -> EaseRating:
    if score <= 5.5:
        return 1
    if score <= 6.9:
        return 2
    if score <= 8.4:
        return 3
    return 4


def _parse_candidates(raw_items: Any) -> List[CardCandidate]:
    out: List[CardCandidate] = []
    if not isinstance(raw_items, list):
        return out
    for item in raw_items[:3]:
        if not isinstance(item, dict):
            continue
        kind = str(item.get("kind") or "sentence").strip().lower()
        if kind not in ("sentence", "vocab", "grammar"):
            kind = "sentence"
        text = str(item.get("text") or "").strip()
        if not text:
            continue
        distractors = item.get("distractors")
        if not isinstance(distractors, list):
            distractors = []
        out.append(
            CardCandidate(
                kind=kind,  # type: ignore[arg-type]
                text=text,
                translation=str(item.get("translation") or "").strip(),
                reason=str(item.get("reason") or "").strip(),
                answer=str(item.get("answer") or "").strip(),
                distractors=[str(d).strip() for d in distractors if str(d).strip()][:3],
            )
        )
    return out


def _to_evaluation(data: Dict[str, Any]) -> CardEvaluation:
    raw_score = data.get("score")
    score = round(float(raw_score), 1) if isinstance(raw_score, (int, float)) else 7.0
    score = max(1.0, min(10.0, score))

    raw_ease = data.get("recommended_ease")
    if isinstance(raw_ease, int) and raw_ease in (1, 2, 3, 4):
        ease: EaseRating = raw_ease  # type: ignore[assignment]
    else:
        ease = _score_to_ease(score)

    corrections = data.get("corrections")
    if not isinstance(corrections, list):
        corrections = []
    return CardEvaluation(
        score=score,
        recommended_ease=ease,
        summary=str(data.get("summary") or "").strip() or "피드백 요약 없음",
        corrections=[str(c).strip() for c in corrections if str(c).strip()][:3],
        native_model=str(data.get("native_model") or "").strip(),
        card_candidates=_parse_candidates(data.get("card_candidates")),
    )


class SpeakingCoach:
    def __init__(self, generate_json_fn: Optional[Callable[..., Any]] = None) -> None:
        self._generate_json = generate_json_fn or llm_router.generate_json

    def _ask(self, prompt: str, temperature: float = 0.3) -> CardEvaluation:
        data, route_name = self._generate_json(_SYSTEM_PROMPT, prompt, temperature)
        logger.info("SpeakingCoach answered via route %s", route_name)
        return _to_evaluation(data if isinstance(data, dict) else {})

    def evaluate_card(
        self,
        card: SpeakingCard,
        transcript: str,
        metrics: SpeakingMetrics,
        prior_history: Sequence[Dict[str, Any]] = (),
    ) -> CardEvaluation:
        prior_note = ""
        if prior_history:
            last = prior_history[0]
            prior_note = (
                f"\nPrevious review on this card ({last.get('session_date')}): "
                f"score={last.get('score')}, wpm={last.get('wpm')}, model={last.get('native_model')}"
            )
        user_prompt = f"""
Evaluate this spoken English answer to an Anki Speaking card.
Category: {card.category} | Card type: {"New" if card.is_new else f"Review (reps={card.reps})"}
Question:
{card.prompt_text}{prior_note}

User Transcript: {transcript}
Metrics: duration={metrics.duration_sec}s, words={metrics.word_count}, wpm={metrics.wpm}, fillers={metrics.filler_count}, long_pauses={metrics.long_pause_count}, max_pause={metrics.max_pause_sec}s

Identify ONLY high-value fixes (Korean-English literal translations, awkward verbs/prepositions, vague phrasing).
Suggest recommended_ease for Anki FSRS: 1=Again (struggled/off-topic/severe pauses), 2=Hard (understood but choppy/many literal errors), 3=Good (clear & natural enough), 4=Easy (fluent, idiomatic, crisp).

Return JSON:
{{
  "score": 1.0-10.0,
  "recommended_ease": 1 | 2 | 3 | 4,
  "summary": "2 crisp Korean sentences: fluency/delivery note + one concrete upgrade point",
  "corrections": ["up to 3 items: 'what user said -> natural English (Korean reason)'"],
  "native_model": "1-2 crisp natural native sentences expressing the user's core point cleanly (for TTS playback)",
  "card_candidates": [
    {{
      "kind": "sentence" | "vocab" | "grammar",
      "text": "natural English sentence or expression (for grammar, full corrected sentence)",
      "translation": "natural Korean translation",
      "reason": "short Korean note why this helps",
      "answer": "only if kind==grammar: exact single-occurrence token to blank",
      "distractors": ["only if kind==grammar: user's wrong form"]
    }}
  ]
}}
Limit card_candidates to 0-2 genuinely useful expressions the user stumbled on.
"""
        return self._ask(user_prompt, temperature=0.3)

    def evaluate_retry(
        self,
        card: SpeakingCard,
        first_transcript: str,
        first_metrics: SpeakingMetrics,
        retry_transcript: str,
        retry_metrics: SpeakingMetrics,
    ) -> CardEvaluation:
        user_prompt = f"""
Compare Attempt 1 vs Retry Attempt on the same Anki Speaking card.
Question:
{card.prompt_text}

Attempt 1 ({first_metrics.duration_sec}s, {first_metrics.wpm} WPM, {first_metrics.filler_count} fillers): {first_transcript}
Retry ({retry_metrics.duration_sec}s, {retry_metrics.wpm} WPM, {retry_metrics.filler_count} fillers): {retry_transcript}

Return JSON:
{{
  "score": 1.0-10.0,
  "recommended_ease": 1 | 2 | 3 | 4,
  "summary": "2 crisp Korean sentences comparing Retry vs Attempt 1 (clarity, hesitation drop, corrections applied)",
  "corrections": ["up to 2 remaining rough spots if any"],
  "native_model": "1-2 tight native sentences if helpful, else empty string",
  "card_candidates": [
    {{
      "kind": "sentence" | "vocab",
      "text": "0-1 high-value upgrade if needed",
      "translation": "Korean translation",
      "reason": "short note"
    }}
  ]
}}
"""
        return self._ask(user_prompt, temperature=0.3)

    def analyze_debrief(self, transcript: str) -> CardEvaluation:
        user_prompt = f"""
The user just finished a real-life or external AI English conversation and recorded a quick voice debrief
(in English, Korean, or mixed) describing what they struggled to say or wanted to express better.
Debrief transcript: {transcript}

Extract 2-4 crisp, natural native English expressions/sentences they should save to Anki.
Return JSON:
{{
  "score": 7.0,
  "recommended_ease": 3,
  "summary": "2 crisp Korean sentences summarizing the target nuance and situational phrasing tip",
  "corrections": ["up to 3 situational phrasing notes in Korean"],
  "native_model": "the single best natural English sentence from the set (for TTS playback)",
  "card_candidates": [
    {{
      "kind": "sentence" | "vocab",
      "text": "natural English sentence or expression",
      "translation": "natural Korean translation",
      "reason": "situation/nuance note"
    }}
  ]
}}
"""
        return self._ask(user_prompt, temperature=0.3)
