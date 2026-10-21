import os
import io
import re
import html
import uuid
import base64
import logging
import subprocess
import concurrent.futures
from typing import List, Dict, Any, Optional

import gtts
from config import (
    ANKI_URL, DECK_SENTENCE, MODEL_SENTENCE, DECK_VOCAB, MODEL_VOCAB, DECK_GRAMMAR, MODEL_GRAMMAR,
    AUDIO_ADDER_MAX_WORKERS, NOTE_TYPES_CONFIG
)
from integrations.anki_connect import AnkiConnector
from integrations.audio import AnkiTTSFiller
from core.completer import NoteCompleter, normalize_vocab_placeholders
from core.link_manager import LinkManager
from backend.schemas.cards import (
    SentenceCreateRequest, SentenceBulkCreateRequest,
    VocabCreateRequest, VocabBulkCreateRequest, GrammarCreateRequest,
    CardResponse, BulkCardResponse, CardStatusResponse
)

logger = logging.getLogger("CardService")

_audio_executor = concurrent.futures.ThreadPoolExecutor(
    max_workers=AUDIO_ADDER_MAX_WORKERS,
    thread_name_prefix="anki_audio"
)

def queue_background_audio(note_id: int, text: str, is_sentence: bool = True) -> None:
    """백그라운드에서 TTS 오디오를 비동기로 생성하여 카드의 '소리' 필드에 안전하게 연결"""
    def _worker():
        try:
            if is_sentence:
                sound_tag = generate_sentence_audio(text)
            else:
                sound_tag, _ = AnkiTTSFiller.generate_gtts(text)
            if sound_tag:
                AnkiConnector.update_note_fields(note_id, {"소리": sound_tag})
                logger.info(f"Background audio attached to note {note_id}: {sound_tag}")
        except Exception as e:
            logger.warning(f"Background audio generation failed for note {note_id}: {e}")

    _audio_executor.submit(_worker)

_tts_client = None
try:
    from google.cloud import texttospeech
    _tts_client = texttospeech.TextToSpeechClient()
except Exception as e:
    logger.warning(f"GCP TTS Client unavailable, using gTTS: {e}")


def check_anki_status() -> CardStatusResponse:
    try:
        AnkiConnector.invoke("deckNames")
        connected = True
    except Exception:
        connected = False
    return CardStatusResponse(
        anki_connected=connected,
        gateway="Anki Manager Central Gateway v2",
        anki_url=ANKI_URL
    )


def launch_anki_app() -> Dict[str, Any]:
    try:
        subprocess.run(["open", "-a", "Anki"], check=True)
        return {"success": True, "message": "Anki launched successfully"}
    except Exception as e:
        logger.error(f"Failed to launch Anki: {e}")
        return {"success": False, "error": str(e)}


def generate_sentence_audio(text: str) -> str:
    clean_text = text.strip()
    if not clean_text:
        return ""

    # 1. Try GCP Chirp3-HD / Studio voices
    global _tts_client
    if _tts_client is not None:
        try:
            sound_tag, _ = AnkiTTSFiller.generate_random_tts(_tts_client, clean_text)
            if sound_tag:
                return sound_tag
        except Exception as err:
            logger.warning(f"GCP TTS failed for '{clean_text}': {err}")

    # 2. Fallback to gTTS
    try:
        sound_tag, _ = AnkiTTSFiller.generate_gtts(clean_text)
        return sound_tag
    except Exception as e:
        logger.error(f"gTTS fallback error: {e}")
        return ""


def add_notes_skipping_failures(notes: List[Dict[str, Any]]) -> List[Optional[int]]:
    """notes와 같은 순서로 note id(추가 못 한 것은 None)를 돌려준다.

    AnkiConnect addNotes는 하나라도 실패하면 배치 전체를 롤백하므로,
    canAddNotes로 추가 가능한 노트만 골라 넣는다.
    """
    if not notes:
        return []
    can_add = AnkiConnector.invoke("canAddNotes", notes=notes) or [False] * len(notes)
    addable = [n for n, ok in zip(notes, can_add) if ok]
    try:
        added_ids = iter(AnkiConnector.invoke("addNotes", notes=addable) or []) if addable else iter(())
        return [next(added_ids, None) if ok else None for ok in can_add]
    except Exception as e:
        # 확인과 추가 사이에 상태가 바뀐 경우: 한 장씩 추가
        logger.warning(f"addNotes batch failed, falling back to one-by-one: {e}")
        results: List[Optional[int]] = []
        for n, ok in zip(notes, can_add):
            if not ok:
                results.append(None)
                continue
            try:
                results.append(AnkiConnector.invoke("addNote", note=n))
            except Exception:
                results.append(None)
        return results


def clean_vocab_example(example: str) -> str:
    """예문에서 불필요한 마크다운 및 태그 정제"""
    if not example:
        return ""
    cleaned = re.sub(r'<\/?b>', '', example)
    cleaned = re.sub(r'\*\*(.*?)\*\*', r'\1', cleaned)
    return cleaned.strip()


def create_sentence_card(req: SentenceCreateRequest) -> CardResponse:
    text = req.sentence.strip()
    if not text:
        return CardResponse(success=False, error="Sentence cannot be empty")

    translation = req.translation.strip() if req.translation else ""

    # 1. Enrich translation if missing
    if not translation and req.auto_enrich:
        try:
            completer = NoteCompleter()
            res = completer.enrich_sentences([text])
            if res and isinstance(res[0], dict) and "해설" in res[0]:
                translation = res[0]["해설"]
        except Exception as e:
            logger.warning(f"AI translation enrichment failed: {e}")

    fields = {
        "문장": text,
        "해설": translation,
        "소리": ""
    }

    try:
        note_id = AnkiConnector.add_note(
            deck_name=DECK_SENTENCE,
            model_name=MODEL_SENTENCE,
            fields=fields,
            options={"allowDuplicate": False}
        )

        # 백그라운드 비동기 오디오 큐 등록 (사용자 대기 시간 0초)
        if req.generate_audio and note_id:
            queue_background_audio(note_id, text, is_sentence=True)

        # Real-time incremental link indexing
        try:
            LinkManager.index_single_sentence(note_id, text)
        except Exception as link_err:
            logger.warning(f"Incremental link indexing warning: {link_err}")

        return CardResponse(
            success=True,
            note_id=note_id,
            data={"sentence": text, "translation": translation, "sound": "queued"}
        )
    except Exception as e:
        err_msg = str(e)
        if "duplicate" in err_msg.lower():
            return CardResponse(
                success=True,
                duplicate=True,
                data={"sentence": text, "translation": translation}
            )
        logger.error(f"Error creating sentence card: {e}")
        return CardResponse(success=False, error=err_msg)


def create_bulk_sentences(req: SentenceBulkCreateRequest) -> BulkCardResponse:
    if not req.items:
        return BulkCardResponse(success=True, count=0, total=0)

    # 1. Ensure translations across all items
    items_to_process = []
    missing_indices = []
    for i, item in enumerate(req.items):
        s = item.sentence.strip()
        t = item.translation.strip() if item.translation else ""
        items_to_process.append({"sentence": s, "translation": t})
        if not t and req.auto_enrich and s:
            missing_indices.append(i)

    if missing_indices and req.auto_enrich:
        try:
            completer = NoteCompleter()
            sentences_to_enrich = [items_to_process[i]["sentence"] for i in missing_indices]
            enriched = completer.enrich_sentences(sentences_to_enrich)
            if enriched and len(enriched) == len(missing_indices):
                for orig_idx, enr in zip(missing_indices, enriched):
                    if isinstance(enr, dict) and "해설" in enr:
                        items_to_process[orig_idx]["translation"] = enr["해설"]
        except Exception as e:
            logger.warning(f"Bulk AI translation enrichment warning: {e}")

    # 2. Process in chunks of 50 (Instant addNotes without audio blocking)
    CHUNK_SIZE = 50
    chunks = [items_to_process[i:i + CHUNK_SIZE] for i in range(0, len(items_to_process), CHUNK_SIZE)]
    total_success_count = 0
    total_skipped = 0

    for chunk in chunks:
        chunk_payload = []
        raw_sentences = []
        for item in chunk:
            s = item["sentence"]
            t = item["translation"]
            if s:
                chunk_payload.append({
                    "deckName": DECK_SENTENCE,
                    "modelName": MODEL_SENTENCE,
                    "fields": {
                        "문장": s,
                        "해설": t,
                        "소리": ""
                    },
                    "options": {"allowDuplicate": False}
                })
                raw_sentences.append(s)

        if not chunk_payload:
            continue

        try:
            results = add_notes_skipping_failures(chunk_payload)
            total_skipped += sum(1 for nid in results if not nid)
            for nid, s_text in zip(results, raw_sentences):
                if nid:
                    total_success_count += 1
                    # 백그라운드 오디오 큐 등록
                    if req.generate_audio:
                        queue_background_audio(nid, s_text, is_sentence=True)
                    try:
                        LinkManager.index_single_sentence(nid, s_text)
                    except Exception:
                        pass
        except Exception as chunk_err:
            logger.error(f"Error adding sentence chunk: {chunk_err}")

    return BulkCardResponse(success=True, count=total_success_count, total=len(req.items), skipped=total_skipped)


def create_vocab_card(req: VocabCreateRequest) -> CardResponse:
    norm_word = normalize_vocab_placeholders(req.word.strip())
    if not norm_word:
        return CardResponse(success=False, error="Word cannot be empty")

    meaning = req.meaning.strip() if req.meaning else ""
    pos = req.pos.strip() if req.pos else ""
    example = clean_vocab_example(req.example.strip() if req.example else "")
    explanation = req.explanation.strip() if req.explanation else ""

    # 1. AI Enrichment if needed
    if req.auto_enrich and (not meaning or not example):
        try:
            completer = NoteCompleter()
            enriched = completer.enrich_vocab([{"단어": norm_word, "뜻": meaning}])
            if enriched and len(enriched) > 0:
                v = enriched[0]
                if not meaning:
                    meaning = v.get("뜻", "")
                if not pos:
                    pos = v.get("품사", "")
                if not example:
                    example = clean_vocab_example(v.get("예문", ""))
                if not explanation:
                    explanation = v.get("설명", "")
        except Exception as e:
            logger.warning(f"AI vocab enrichment failed: {e}")

    fields = {
        "단어": norm_word,
        "뜻": meaning,
        "품사": pos,
        "유의어": "",  # STRICT ZERO-SYNONYM RULE!
        "예문": example,
        "설명": explanation,
        "소리": ""
    }

    from backend.services.corpus_service import evaluate_expression_rank_and_tier
    _, freq_tier = evaluate_expression_rank_and_tier(norm_word)

    try:
        note_id = AnkiConnector.add_note(
            deck_name=DECK_VOCAB,
            model_name=MODEL_VOCAB,
            fields=fields,
            tags=[freq_tier],
            options={"allowDuplicate": False}
        )

        # 백그라운드 비동기 오디오 큐 등록
        if req.generate_audio and note_id:
            queue_background_audio(note_id, norm_word, is_sentence=False)

        # Real-time incremental link indexing
        try:
            LinkManager.index_single_vocab(note_id, norm_word, meaning, pos)
        except Exception as link_err:
            logger.warning(f"Incremental vocab link indexing warning: {link_err}")

        return CardResponse(
            success=True,
            note_id=note_id,
            data={"word": norm_word, "meaning": meaning, "pos": pos}
        )
    except Exception as e:
        err_msg = str(e)
        if "duplicate" in err_msg.lower():
            return CardResponse(
                success=True,
                duplicate=True,
                error="이미 Anki에 등록된 단어/표현입니다 (중복 방지)",
                data={"word": norm_word}
            )
        logger.error(f"Error creating vocab card: {e}")
        return CardResponse(success=False, error=err_msg)


def create_bulk_vocabs(req: VocabBulkCreateRequest) -> BulkCardResponse:
    if not req.items:
        return BulkCardResponse(success=True, count=0, total=0)

    CHUNK_SIZE = 50
    chunks = [req.items[i:i + CHUNK_SIZE] for i in range(0, len(req.items), CHUNK_SIZE)]
    total_success_count = 0
    total_skipped = 0

    for chunk in chunks:
        chunk_payload = []
        raw_items = []
        for item in chunk:
            raw_word = item.word.strip()
            norm_word = normalize_vocab_placeholders(raw_word)
            if not norm_word:
                continue

            meaning = item.meaning.strip() if item.meaning else ""
            pos = item.pos.strip() if item.pos else ""
            example = clean_vocab_example(item.example.strip() if item.example else "")
            explanation = item.explanation.strip() if item.explanation else ""

            from backend.services.corpus_service import evaluate_expression_rank_and_tier
            _, freq_tier = evaluate_expression_rank_and_tier(norm_word)

            chunk_payload.append({
                "deckName": DECK_VOCAB,
                "modelName": MODEL_VOCAB,
                "fields": {
                    "단어": norm_word,
                    "뜻": meaning,
                    "품사": pos,
                    "유의어": "",
                    "예문": example,
                    "설명": explanation,
                    "소리": ""
                },
                "tags": [freq_tier],
                "options": {"allowDuplicate": False}
            })
            raw_items.append((norm_word, meaning, pos))

        if not chunk_payload:
            continue

        try:
            results = add_notes_skipping_failures(chunk_payload)
            total_skipped += sum(1 for nid in results if not nid)
            for nid, (w, m, p) in zip(results, raw_items):
                if nid:
                    total_success_count += 1
                    # 백그라운드 오디오 큐 등록
                    if req.generate_audio:
                        queue_background_audio(nid, w, is_sentence=False)
                    try:
                        LinkManager.index_single_vocab(nid, w, m, p)
                    except Exception:
                        pass
        except Exception as chunk_err:
            logger.error(f"Error adding vocab chunk: {chunk_err}")

    return BulkCardResponse(success=True, count=total_success_count, total=len(req.items), skipped=total_skipped)


GRAMMAR_OPTION_FIELDS = ["보기1", "보기2", "보기3"]


def _answer_occurrences(sentence: str, answer: str) -> int:
    """English Grammar 앞면 템플릿과 같은 규칙(\\b정답\\b, 대소문자 무시)으로 빈칸이 몇 곳 생기는지 센다."""
    if not answer:
        return 0
    return len(re.findall(r"\b" + re.escape(answer) + r"\b", sentence, flags=re.IGNORECASE))


def create_grammar_card(req: GrammarCreateRequest) -> CardResponse:
    """문법 객관식 카드: 문장 속 정답이 빈칸이 되고, 보기1~3 + 정답 네 개가 선택지가 된다."""
    sentence = req.sentence.strip()
    answer = (req.answer or "").strip()
    if not sentence:
        return CardResponse(success=False, error="Sentence cannot be empty")
    hits = _answer_occurrences(sentence, answer)
    if hits == 0:
        return CardResponse(success=False, error=f"정답 '{answer}'이(가) 문장 안에 단어 단위로 없습니다. 빈칸을 만들 수 없습니다.")
    if hits > 1:
        return CardResponse(success=False, error=f"정답 '{answer}'이(가) 문장에 {hits}번 나옵니다. 빈칸이 한 번만 생기도록 정답을 더 길게 잡으세요.")

    # 주어진 오답: 앞뒤 공백 제거, 정답·서로와 겹치는 것 제거, 최대 3개
    seen = {answer.lower()}
    distractors = []
    for d in req.distractors:
        d = (d or "").strip()
        if d and d.lower() not in seen:
            seen.add(d.lower())
            distractors.append(d)
    fields = {"문장": sentence, "정답": answer, "해설": (req.translation or "").strip(),
              "설명": (req.explanation or "").strip(), "소리": ""}
    for name, value in zip(GRAMMAR_OPTION_FIELDS, distractors[:3]):
        fields[name] = value

    missing = [k for k in ["해설", "설명", *GRAMMAR_OPTION_FIELDS] if not fields.get(k)]
    if missing and req.auto_enrich:
        current = {k: v for k, v in fields.items() if v and k != "소리"}
        try:
            # complete_fields_batch는 반환 형식을 명시한다 (complete_fields는 시스템 지침의 다른 스키마로 답한다)
            generated = NoteCompleter().complete_fields_batch(
                MODEL_GRAMMAR, [{"id": 1, "main": sentence, "current": current, "missing": missing}]).get("1") or {}
        except Exception as e:
            logger.warning(f"Grammar enrichment failed: {e}")
            generated = {}
        for k in missing:
            v = generated.get(k)
            if isinstance(v, str) and v.strip():
                fields[k] = html.unescape(v.strip())

    options = [fields.get(k, "") for k in GRAMMAR_OPTION_FIELDS] + [answer]
    if any(not o for o in options) or len({o.lower() for o in options}) != 4:
        return CardResponse(success=False, error=f"선택지 네 개가 서로 다르게 채워지지 않았습니다: {options}")
    if not fields["해설"] or not fields["설명"]:
        return CardResponse(success=False, error="해설 또는 설명을 만들지 못했습니다.")

    data = {k: v for k, v in fields.items() if k != "소리"}
    try:
        note_id = AnkiConnector.add_note(
            deck_name=DECK_GRAMMAR,
            model_name=MODEL_GRAMMAR,
            fields=fields,
            options={"allowDuplicate": False}
        )
    except Exception as e:
        if "duplicate" in str(e).lower():
            return CardResponse(success=True, duplicate=True, data=data)
        logger.error(f"Error creating grammar card: {e}")
        return CardResponse(success=False, error=str(e))

    if req.generate_audio and note_id:
        queue_background_audio(note_id, sentence, is_sentence=True)
    try:
        LinkManager.index_single_sentence(note_id, sentence)
    except Exception as link_err:
        logger.warning(f"Incremental link indexing warning: {link_err}")
    _assign_card_decks(note_id, MODEL_GRAMMAR)
    return CardResponse(success=True, note_id=note_id, data=data)


def _assign_card_decks(note_id: int, model_name: str) -> None:
    """addNote는 모든 카드를 한 덱에 넣는다. config의 deck_assignment대로 바로 옮긴다 (정리 작업과 같은 규칙)."""
    for rule in NOTE_TYPES_CONFIG.get(model_name, {}).get("deck_assignment", []):
        try:
            cards = AnkiConnector.invoke(
                "findCards", query=f'nid:{note_id} card:"{rule["card"]}" -deck:"{rule["target"]}"')
            if cards:
                AnkiConnector.invoke("changeDeck", cards=cards, deck=rule["target"])
        except Exception as e:
            logger.warning(f"Deck assignment for note {note_id} ({rule}) failed: {e}")
