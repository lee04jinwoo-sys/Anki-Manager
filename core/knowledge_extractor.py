import os
import json
import re
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")

from config import (
    KNOWLEDGE_EXTRACTOR_MODEL,
    MODEL_KNOWLEDGE,
    DECK_KNOWLEDGE,
    GEMINI_DEFAULT_TEMPERATURE
)
from integrations.anki_connect import AnkiConnector
from utils.inspector import inspect_items

# --- Pydantic Schemas (English Output) ---

class KnowledgeQACard(BaseModel):
    question: str = Field(description="Front Question in English: Specific, unambiguous, and leading to a single exact answer")
    answer: str = Field(description="Back Answer in English: Crisp, 1-3 words, or short phrase under 15 words")
    explanation: str = Field(description="Why It Matters in English: 2-3 sentences explaining significance, historical context, or causal impact")
    quality_score: int = Field(default=90, ge=0, le=100, description="Self-assessed quality score (0-100)")

class KnowledgeQAResult(BaseModel):
    cards: List[KnowledgeQACard]


class KnowledgeExtractor:
    """
    High-yield Knowledge Q&A flashcard extractor powered by Gemini.
    Generates 100% English cards strictly following SuperMemo 20 Rules:
    Minimum Information Principle (MIP), Zero Ambiguity, 5-Second Rule, and 'Why It Matters' context.
    """

    def __init__(self, pbar=None):
        self.client = genai.Client(api_key=GOOGLE_API_KEY)
        self.model_id = KNOWLEDGE_EXTRACTOR_MODEL
        self.pbar = pbar

    def _log(self, msg: str):
        if self.pbar:
            if hasattr(self.pbar, 'write'):
                self.pbar.write(msg)
            else:
                print(msg)
        else:
            print(msg)

    def _build_sys_instruct(self) -> str:
        return """You are a world-class cognitive science and Spaced Repetition (SuperMemo 20 Rules) expert specializing in creating lifelong knowledge flashcards for Anki.
Your task is to analyze the provided source material and create high-yield, crisp, memorable [Front Question / Back Answer / Why It Matters] cards in fluent, natural English.

Strictly adhere to the following 7 Core Card Design Rules:

[7 Core Card Creation Rules]
1. [Language]: All Questions, Answers, and Explanations MUST be written in natural, clear, high-quality ENGLISH.
2. [Minimum Information Principle (MIP)]: Each card must test exactly ONE atomic concept or causal relationship. Never ask compound/multi-part questions.
3. [Zero Ambiguity & 5-Second Rule]:
   - Questions must contain sufficient context, constraints, and clues so that exactly ONE definitive answer is possible.
   - Avoid vague open-ended prompts like "Explain X" or "What happened to Y?".
   - The user must be able to recall the answer within 3–5 seconds upon reading the front.
4. [Crisp, Short Answer]:
   - The answer must be 1–3 words, a proper noun/term, or a very concise phrase (under 15 words).
   - If applicable, include original Greek/Latin/foreign term in parentheses (e.g., "Titanomachy (Titanomachia)").
5. [Why It Matters (Explanation)]:
   - Provide 2–3 sentences highlighting WHY this fact/concept is historically, philosophically, or practically significant.
   - Explain the causal consequence, historical impact, or cultural legacy so it anchors into long-term memory.
6. [Skip Trivial / Obvious Facts]:
   - Do not generate cards for elementary common knowledge (e.g., "Zeus is a Greek god", "The Earth orbits the Sun").
7. [Output Format]:
   - Return a JSON object with a 'cards' array containing card objects."""

    def _extract_single_chunk(self, chunk_text: str, count: int, source_label: str = "", section_info: str = "") -> List[Dict[str, Any]]:
        """Calls Gemini API on a single chunk to extract English Q&A cards."""
        sys_instruct = self._build_sys_instruct()
        section_note = f" (Section: {section_info})" if section_info else ""

        prompt = f"""
Analyze the following source text{section_note} and generate exactly {count} atomic, high-yield Knowledge Q&A flashcards in English.

[Source Title / URL]: {source_label or 'Provided Material'}

[Source Text]:
{chunk_text}

[Instructions]:
1. Create exactly {count} cards in fluent English.
2. Follow all 7 Core Card Design Rules strictly:
   - 'question': Clear, specific question with zero ambiguity.
   - 'answer': Crisp, concise 1-3 word answer.
   - 'explanation': 2-3 sentences explaining 'Why It Matters' (context & significance).
3. Return as a JSON object with key 'cards'.
"""

        try:
            response = self.client.models.generate_content(
                model=self.model_id,
                contents=[sys_instruct, prompt],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.3
                )
            )

            res_json = json.loads(response.text)
            raw_cards = res_json.get("cards", []) if isinstance(res_json, dict) else res_json

            formatted = []
            for c in raw_cards:
                if not isinstance(c, dict):
                    continue
                q = c.get("question") or c.get("질문") or ""
                a = c.get("answer") or c.get("정답") or ""
                exp = c.get("explanation") or c.get("설명") or c.get("why_it_matters") or ""
                
                # 출처 필드: source_label을 무조건 100% 기본값으로 보장
                src = source_label or c.get("source") or c.get("출처") or "Knowledge Source"

                if q.strip() and a.strip():
                    formatted.append({
                        "질문": q.strip(),
                        "정답": a.strip(),
                        "설명": exp.strip(),
                        "출처": src.strip()
                    })
            return formatted

        except Exception as e:
            self._log(f"❌ Extraction error on chunk: {e}")
            return []

    def extract_qa_cards(self, text: str, target_count: int = 10, source_label: str = "") -> List[Dict[str, Any]]:
        """
        Extracts target_count English Q&A cards from text, handling long text automatically.
        """
        from collectors.knowledge_fetcher import KnowledgeFetcher

        text_len = len(text)

        # 1. Single pass for <= 10,000 chars
        if text_len <= 10000:
            self._log(f"🧠 Gemini ({self.model_id}) generating {target_count} English Q&A cards... ({text_len} chars)")
            return self._extract_single_chunk(text, target_count, source_label)

        # 2. Chunking for long text (> 10,000 chars)
        chunks = KnowledgeFetcher.chunk_by_paragraphs(text, target_chunk_size=7000)
        num_chunks = len(chunks)
        self._log(f"📚 Long text detected ({text_len} chars, split into {num_chunks} sections). Distributing card extraction...")

        base_count = target_count // num_chunks
        remainder = target_count % num_chunks

        all_cards = []
        for idx, chunk in enumerate(chunks, 1):
            chunk_target = base_count + (1 if idx <= remainder else 0)
            if chunk_target <= 0:
                continue

            section_label = f"{idx}/{num_chunks}"
            self._log(f"  👉 Processing section [{idx}/{num_chunks}] (Target: {chunk_target} cards, {len(chunk)} chars)...")
            cards = self._extract_single_chunk(chunk, chunk_target, source_label, section_info=section_label)
            all_cards.extend(cards)

        self._log(f"✨ Extraction complete: Total {len(all_cards)} English Q&A cards generated.")
        return all_cards


def run_knowledge_workflow(
    input_data: str,
    target_count: int = 10,
    is_web: bool = False,
    pbar = None
) -> bool:
    """
    Runs the complete Knowledge Q&A workflow.
    1. Fetch content from URL/Text
    2. Extract English Q&A cards via Gemini
    3. Interactive CLI inspection
    4. Save to Anki Knowledge deck with clean Source field
    """
    from collectors.knowledge_fetcher import KnowledgeFetcher

    print(f"\n📚 [Knowledge Q&A] Loading content...")
    fetch_res = KnowledgeFetcher.fetch_from_input(input_data)
    if not fetch_res or not fetch_res.get("content"):
        print("❌ Could not load content. Please check the URL, file path, or text.")
        return False

    content = fetch_res["content"]
    source_label = fetch_res.get("source", "Direct Input")
    print(f"✅ Content loaded: '{source_label}' ({len(content)} characters)")

    # Extract English Q&A
    extractor = KnowledgeExtractor(pbar=pbar)
    cards = extractor.extract_qa_cards(content, target_count=target_count, source_label=source_label)

    if not cards:
        print("⚠️ No cards generated.")
        return False

    # Interactive inspection
    final_cards = cards
    if not is_web:
        print("\n🔍 Review generated cards (Space/Enter to toggle, C to confirm):")
        final_cards = inspect_items(
            cards,
            display_func=lambda x: f"Q: {x.get('질문', '')} ➔ A: {x.get('정답', '')}"
        )

    if not final_cards:
        print("ℹ️ No cards selected. Cancelled.")
        return False

    # Save to Anki
    print(f"\n💾 Saving {len(final_cards)} cards to Anki '{DECK_KNOWLEDGE}' deck...")

    AnkiConnector.invoke('createDeck', deck=DECK_KNOWLEDGE)

    anki_notes = []
    for card in final_cards:
        anki_notes.append({
            "deckName": DECK_KNOWLEDGE,
            "modelName": MODEL_KNOWLEDGE,
            "fields": {
                "질문": card["질문"],
                "정답": card["정답"],
                "설명": card.get("설명", ""),
                "출처": card.get("출처", source_label)
            },
            "options": {"allowDuplicate": False}
        })

    try:
        results = AnkiConnector.add_notes(anki_notes)
        success_count = sum(1 for r in results if r is not None)
        dup_count = len(results) - success_count
        print(f"🎉 Success: {success_count} cards added to Anki! (Duplicates/Skipped: {dup_count})")
        return True
    except Exception as e:
        print(f"❌ Error saving to Anki: {e}")
        return False
