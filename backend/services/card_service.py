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
    ANKI_URL, DECK_SENTENCE, MODEL_SENTENCE, DECK_VOCAB, MODEL_VOCAB
)
from integrations.anki_connect import AnkiConnector
from integrations.audio import AnkiTTSFiller
from core.completer import NoteCompleter, normalize_vocab_placeholders
from core.link_manager import LinkManager
from backend.schemas.cards import (
    SentenceCreateRequest, SentenceBulkCreateRequest,
    VocabCreateRequest, VocabBulkCreateRequest,
    CardResponse, BulkCardResponse, CardStatusResponse
)

logger = logging.getLogger("CardService")

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

    # 2. Generate Audio
    sound_tag = ""
    if req.generate_audio:
        sound_tag = generate_sentence_audio(text)

    fields = {
        "문장": text,
        "해설": translation,
        "소리": sound_tag
    }

    try:
        note_id = AnkiConnector.add_note(
            deck_name=DECK_SENTENCE,
            model_name=MODEL_SENTENCE,
            fields=fields,
            options={"allowDuplicate": False}
        )
        # Real-time incremental link indexing
        try:
            LinkManager.index_single_sentence(note_id, text)
        except Exception as link_err:
            logger.warning(f"Incremental link indexing warning: {link_err}")

        return CardResponse(
            success=True,
            note_id=note_id,
            data={"sentence": text, "translation": translation, "sound": sound_tag}
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

    # 2. Process in chunks of 20 to prevent HTTP timeouts and allow progress
    CHUNK_SIZE = 20
    chunks = [items_to_process[i:i + CHUNK_SIZE] for i in range(0, len(items_to_process), CHUNK_SIZE)]
    total_success_count = 0

    def build_note(item):
        s = item["sentence"]
        t = item["translation"]
        if not s:
            return None
        sound_tag = generate_sentence_audio(s) if req.generate_audio else ""
        return {
            "deckName": DECK_SENTENCE,
            "modelName": MODEL_SENTENCE,
            "fields": {
                "문장": s,
                "해설": t,
                "소리": sound_tag
            },
            "options": {"allowDuplicate": False},
            "_raw_sentence": s
        }

    for chunk in chunks:
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            chunk_payload = list(filter(None, executor.map(build_note, chunk)))

        if not chunk_payload:
            continue

        raw_sentences = [n.pop("_raw_sentence") for n in chunk_payload]

        try:
            results = AnkiConnector.invoke("addNotes", notes=chunk_payload)
            for nid, s_text in zip(results or [], raw_sentences):
                if nid:
                    total_success_count += 1
                    try:
                        LinkManager.index_single_sentence(nid, s_text)
                    except Exception:
                        pass
        except Exception as chunk_err:
            logger.error(f"Error adding sentence chunk: {chunk_err}")

    return BulkCardResponse(success=True, count=total_success_count, total=len(req.items))


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

    # 2. Audio generation (STRICT RULE: English Vocabulary MUST use gTTS)
    sound_tag = ""
    if req.generate_audio:
        try:
            sound_tag, _ = AnkiTTSFiller.generate_gtts(norm_word)
        except Exception as e:
            logger.warning(f"Vocab gTTS generation warning: {e}")

    fields = {
        "단어": norm_word,
        "뜻": meaning,
        "품사": pos,
        "유의어": "",  # STRICT ZERO-SYNONYM RULE!
        "예문": example,
        "설명": explanation,
        "소리": sound_tag
    }

    try:
        note_id = AnkiConnector.add_note(
            deck_name=DECK_VOCAB,
            model_name=MODEL_VOCAB,
            fields=fields,
            options={"allowDuplicate": False}
        )
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

    def process_item(item):
        raw_word = item.word.strip()
        norm_word = normalize_vocab_placeholders(raw_word)
        if not norm_word:
            return None

        meaning = item.meaning.strip() if item.meaning else ""
        pos = item.pos.strip() if item.pos else ""
        example = clean_vocab_example(item.example.strip() if item.example else "")
        explanation = item.explanation.strip() if item.explanation else ""

        sound_tag = ""
        if req.generate_audio:
            try:
                sound_tag, _ = AnkiTTSFiller.generate_gtts(norm_word)
            except Exception as e:
                logger.warning(f"Bulk vocab gTTS warning for '{norm_word}': {e}")

        return {
            "deckName": DECK_VOCAB,
            "modelName": MODEL_VOCAB,
            "fields": {
                "단어": norm_word,
                "뜻": meaning,
                "품사": pos,
                "유의어": "",  # STRICT ZERO-SYNONYM RULE!
                "예문": example,
                "설명": explanation,
                "소리": sound_tag
            },
            "options": {"allowDuplicate": False},
            "_raw_data": (norm_word, meaning, pos)
        }

    CHUNK_SIZE = 20
    chunks = [req.items[i:i + CHUNK_SIZE] for i in range(0, len(req.items), CHUNK_SIZE)]
    total_success_count = 0

    for chunk in chunks:
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            chunk_payload = list(filter(None, executor.map(process_item, chunk)))

        if not chunk_payload:
            continue

        raw_items = [n.pop("_raw_data") for n in chunk_payload]

        try:
            results = AnkiConnector.invoke("addNotes", notes=chunk_payload)
            for nid, (w, m, p) in zip(results or [], raw_items):
                if nid:
                    total_success_count += 1
                    try:
                        LinkManager.index_single_vocab(nid, w, m, p)
                    except Exception:
                        pass
        except Exception as chunk_err:
            logger.error(f"Error adding vocab chunk: {chunk_err}")

    return BulkCardResponse(success=True, count=total_success_count, total=len(req.items))

