"""LLM speaking coach built on top of core.llm_router.generate_json."""
from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional, Sequence

from core import llm_router
from speaking.models import CardCandidate, CoachFeedback, SpeakingMetrics

logger = logging.getLogger("speaking.coach")

_SYSTEM_PROMPT = (
    "You are a concise, objective English speaking coach for a B2-C1 Korean university student "
    "in Toronto preparing for campus life, tech internships, and IELTS/TOEFL Speaking. "
    "Respond ONLY with valid JSON matching the requested schema. "
    "Write feedback explanations in crisp Korean without flattery or filler praise."
)


def _parse_candidates(raw_items: Any) -> List[CardCandidate]:
    out: List[CardCandidate] = []
    if not isinstance(raw_items, list):
        return out
    for item in raw_items[:4]:
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


def _to_feedback(data: Dict[str, Any]) -> CoachFeedback:
    raw_score = data.get("score")
    score: Optional[float] = None
    if isinstance(raw_score, (int, float)):
        score = round(float(raw_score), 1)
    corrections = data.get("corrections")
    if not isinstance(corrections, list):
        corrections = []
    return CoachFeedback(
        summary=str(data.get("summary") or "").strip() or "피드백 요약 없음",
        score=score,
        corrections=[str(c).strip() for c in corrections if str(c).strip()][:5],
        native_model=str(data.get("native_model") or "").strip(),
        followup_question=(str(data.get("followup_question")).strip() if data.get("followup_question") else None),
        card_candidates=_parse_candidates(data.get("card_candidates")),
    )


class SpeakingCoach:
    def __init__(
        self,
        generate_json_fn: Optional[Callable[..., Any]] = None,
    ) -> None:
        self._generate_json = generate_json_fn or llm_router.generate_json

    def _ask(self, prompt: str, temperature: float = 0.3) -> CoachFeedback:
        data, route_name = self._generate_json(_SYSTEM_PROMPT, prompt, temperature)
        logger.info("SpeakingCoach answered via route %s", route_name)
        return _to_feedback(data if isinstance(data, dict) else {})

    def evaluate_warmup(
        self,
        prompt: str,
        transcript: str,
        metrics: SpeakingMetrics,
    ) -> CoachFeedback:
        user_prompt = f"""
Evaluate this 30-45s English warmup response. Keep it ultra-brief so the user stays in momentum.
Prompt: {prompt}
Transcript: {transcript}
Metrics: duration={metrics.duration_sec}s, wpm={metrics.wpm}, fillers={metrics.filler_count}, long_pauses={metrics.long_pause_count}

Return JSON:
{{
  "summary": "1-2 sentences in Korean on flow and one quick tip",
  "score": 1.0-10.0,
  "corrections": ["up to 2 brief 'before -> natural fix' items"],
  "native_model": "1 crisp natural sentence upgrading the user's core point",
  "followup_question": null,
  "card_candidates": []
}}
"""
        return self._ask(user_prompt, temperature=0.3)

    def evaluate_main_pass1(
        self,
        prompt: str,
        track: str,
        mission_vocab: Sequence[str],
        transcript: str,
        metrics: SpeakingMetrics,
    ) -> CoachFeedback:
        vocab_str = ", ".join(mission_vocab) if mission_vocab else "(none)"
        rubric = {
            "interview": "STAR clarity, technical specificity, concise impact",
            "ielts": "clear stance, logical development, natural discourse markers, lexical range",
            "daily": "natural conversational tone, directness, idiomatic phrasing",
        }.get(track, "fluency, clarity, natural phrasing")

        user_prompt = f"""
Evaluate Pass 1 (90s) of a 4/3/2 speaking drill.
Track: {track} (focus: {rubric})
Prompt: {prompt}
Optional mission vocab from user's Anki: {vocab_str}
Transcript: {transcript}
Metrics: duration={metrics.duration_sec}s, wpm={metrics.wpm}, fillers={metrics.filler_count}, long_pauses={metrics.long_pause_count}, max_pause={metrics.max_pause_sec}s

Identify ONLY high-value fixes (Korean-English literal translations, awkward verbs/prepositions, vague phrasing).
Return JSON:
{{
  "summary": "2-3 crisp Korean sentences: structure/delivery diagnosis + mission vocab check + 1 focus for the 60s Pass 2 retry",
  "score": 1.0-10.0,
  "corrections": ["up to 4 items: 'what user said -> natural English (Korean reason)'"],
  "native_model": "2-3 natural C1 spoken sentences expressing the user's best point cleanly (for TTS playback)",
  "followup_question": null,
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
Limit card_candidates to 1-3 genuinely useful items the user stumbled on.
"""
        return self._ask(user_prompt, temperature=0.3)

    def evaluate_main_pass2(
        self,
        prompt: str,
        track: str,
        pass1_transcript: str,
        pass1_metrics: SpeakingMetrics,
        pass2_transcript: str,
        pass2_metrics: SpeakingMetrics,
    ) -> CoachFeedback:
        user_prompt = f"""
Compare Pass 1 vs compressed Pass 2 (60s) on the same prompt, then generate 1 unexpected spontaneous follow-up question.
Track: {track}
Prompt: {prompt}
Pass 1 ({pass1_metrics.duration_sec}s, {pass1_metrics.wpm} WPM, {pass1_metrics.filler_count} fillers): {pass1_transcript}
Pass 2 ({pass2_metrics.duration_sec}s, {pass2_metrics.wpm} WPM, {pass2_metrics.filler_count} fillers): {pass2_transcript}

Return JSON:
{{
  "summary": "2-3 crisp Korean sentences comparing Pass 2 vs Pass 1 (did corrections stick, clarity/fluency gain)",
  "score": 1.0-10.0,
  "corrections": ["up to 2 remaining rough spots in Pass 2"],
  "native_model": "1-2 tight native sentences if helpful, else empty string",
  "followup_question": "1 sharp, realistic English follow-up question directly challenging or extending what the user just said",
  "card_candidates": [
    {{
      "kind": "sentence" | "vocab",
      "text": "high-value upgrade if any (0-1 item)",
      "translation": "Korean translation",
      "reason": "short note"
    }}
  ]
}}
"""
        return self._ask(user_prompt, temperature=0.4)

    def evaluate_followup(
        self,
        followup_question: str,
        transcript: str,
        metrics: SpeakingMetrics,
    ) -> CoachFeedback:
        user_prompt = f"""
Evaluate this spontaneous 30-60s follow-up response.
Follow-up question: {followup_question}
Transcript: {transcript}
Metrics: duration={metrics.duration_sec}s, wpm={metrics.wpm}, fillers={metrics.filler_count}, long_pauses={metrics.long_pause_count}

Return JSON:
{{
  "summary": "2 crisp Korean sentences on spontaneous agility and clarity",
  "score": 1.0-10.0,
  "corrections": ["up to 3 items: 'before -> natural fix'"],
  "native_model": "1-2 natural native spoken sentences answering the follow-up cleanly",
  "followup_question": null,
  "card_candidates": [
    {{
      "kind": "sentence" | "vocab" | "grammar",
      "text": "natural English sentence or expression",
      "translation": "Korean translation",
      "reason": "short Korean note",
      "answer": "only if kind==grammar",
      "distractors": []
    }}
  ]
}}
Limit card_candidates to 0-2 high-value items.
"""
        return self._ask(user_prompt, temperature=0.3)

    def analyze_debrief(self, transcript: str) -> CoachFeedback:
        user_prompt = f"""
The user just finished a real-life or external AI English conversation and recorded a quick voice debrief
(in English, Korean, or mixed) describing what they struggled to say or wanted to express better.
Debrief transcript: {transcript}

Extract 2-4 crisp, natural native English expressions/sentences they should save to Anki.
Return JSON:
{{
  "summary": "2 crisp Korean sentences summarizing the target nuance and situational phrasing tip",
  "score": null,
  "corrections": ["up to 3 situational phrasing notes in Korean"],
  "native_model": "the single best natural English sentence from the set (for TTS playback)",
  "followup_question": null,
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
