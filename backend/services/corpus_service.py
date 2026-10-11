from __future__ import annotations

import os
import re
import html
import json
import time
import sqlite3
import logging
import requests
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Any

from google import genai
from google.genai import types
from dotenv import load_dotenv
from utils.settings_manager import get_setting
from nltk.stem import WordNetLemmatizer

from integrations.anki_connect import AnkiConnector
from integrations.audio import AnkiTTSFiller
from core.link_manager import LinkManager
from utils.pos_automator import get_simple_pos
from backend.services import card_service
from backend.schemas.cards import SentenceBulkCreateRequest, SentenceItem
from backend.schemas.corpus import (
    CollocationCandidate, CollocationResponse,
    PromoteChunkRequest, PromoteChunkResponse,
    CorpusAuditStatsResponse
)

load_dotenv()
logger = logging.getLogger("CorpusService")

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"
CORPUS_DB_PATH = DATA_DIR / "frequency_corpus.db"
AUDIT_JSON_PATH = DATA_DIR / "vocab_corpus_audit.json"
PROMOTE_BACKUP_DIR = DATA_DIR / "backups" / "promote"
LLM_CACHE_PATH = DATA_DIR / "llm_cache.db"
COLLOCATION_CACHE_DAYS = 90

lemmatizer = WordNetLemmatizer()

STOPWORDS = {
    'a', 'an', 'the', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'from',
    'about', 'into', 'over', 'after', 'is', 'are', 'be', 'been', 'being', 'have',
    'has', 'had', 'do', 'does', 'did', 'a', 'b', 'c', 'sb', 'sth', 'someone',
    'something', 'somebody', 'sbd', 'v-ing', 'and', 'or', 'not', 'up', 'out', 'off',
    'down', 'it', 'its', 'as', 'that', 'this', 'one', 'ones'
}


def _get_corpus_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(CORPUS_DB_PATH), timeout=5.0)
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    return conn


def get_word_rank(word: str) -> int:
    """단어의 코퍼스 랭킹 조회 (표제어 및 Lemmatization 지원)"""
    w = word.lower().strip()
    if not w or not CORPUS_DB_PATH.exists():
        return 999999

    with _get_corpus_connection() as conn:
        cursor = conn.cursor()
        # 1. exact match
        row = cursor.execute("SELECT rank FROM words WHERE word = ?", (w,)).fetchone()
        if row:
            return row[0]
        # 2. verb lemma
        v_lemma = lemmatizer.lemmatize(w, pos="v")
        if v_lemma != w:
            row = cursor.execute("SELECT rank FROM words WHERE word = ?", (v_lemma,)).fetchone()
            if row:
                return row[0]
        # 3. noun lemma
        n_lemma = lemmatizer.lemmatize(w, pos="n")
        if n_lemma != w:
            row = cursor.execute("SELECT rank FROM words WHERE word = ?", (n_lemma,)).fetchone()
            if row:
                return row[0]
    return 999999


def clean_text(raw_html: str) -> str:
    text = html.unescape(raw_html)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'[\(\)\[\]\{\}\/\\\"\'\,\.\;\:\!\?]', ' ', text)
    return text.strip()


def evaluate_expression_rank_and_tier(raw_text: str) -> Tuple[int, str]:
    """구문이나 단어의 코퍼스 랭킹과 5단계 티어 산출"""
    text = clean_text(raw_text)
    tokens = [t.lower() for t in text.split() if t.strip()]
    if not tokens:
        return 999999, "freq::tier5_rare"

    if len(tokens) == 1:
        rank = get_word_rank(tokens[0])
    else:
        content_tokens = [t for t in tokens if t not in STOPWORDS]
        if not content_tokens:
            content_tokens = tokens
        ranks = [get_word_rank(t) for t in content_tokens]
        rank = max(ranks)

    if rank <= 3000:
        tier = "freq::tier1_essential"
    elif rank <= 10000:
        tier = "freq::tier2_common"
    elif rank <= 25000:
        tier = "freq::tier3_advanced"
    elif rank <= 60000:
        tier = "freq::tier4_academic"
    else:
        tier = "freq::tier5_rare"

    return rank, tier


def fetch_google_1t_tokens(word: str) -> Dict[str, List[str]]:
    """
    Google Web 1T 코퍼스 기반으로 단어 앞/뒤에 가장 빈번하게 결합하는 토큰 추출 (Datamuse API)
    """
    results: Dict[str, List[str]] = {"precursors": [], "followers": []}
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        # Precursors (X + word)
        r_prec = requests.get(f"https://api.datamuse.com/words?rel_bgb={word}&max=8", headers=headers, timeout=3).json()
        precs = [x["word"] for x in r_prec if x.get("word", "").isalpha() and len(x.get("word", "")) > 1]
        results["precursors"] = precs[:5]

        # Followers (word + X)
        r_foll = requests.get(f"https://api.datamuse.com/words?rel_bga={word}&max=8", headers=headers, timeout=3).json()
        folls = [x["word"] for x in r_foll if x.get("word", "").isalpha() and len(x.get("word", "")) > 1]
        results["followers"] = folls[:5]
    except Exception as e:
        logger.warning(f"Google 1T token fetch failed for '{word}': {e}")
    return results


def fetch_google_books_ngram_frequencies(chunks: List[str]) -> Dict[str, float]:
    """
    Google Books Ngram Viewer API를 통해 청크들의 실제 출현 빈도를 배치 쿼리로 측정
    """
    freq_map: Dict[str, float] = {}
    if not chunks:
        return freq_map

    headers = {"User-Agent": "Mozilla/5.0"}
    clean_map: Dict[str, str] = {}
    query_terms = []

    for chk in chunks:
        c = re.sub(r'\(.*?\)', '', chk).strip()
        tokens = c.split()
        filtered = [t for t in tokens if t not in {'A', 'B', 'C', 'X', 'Y'} and t.lower() not in {'sb', 'sth', 'someone', 'something', 'v-ing', 'v'} and not t.endswith("'s")]
        cleaned = " ".join(filtered) if filtered else c
        clean_map[cleaned] = chk
        query_terms.append(cleaned.replace(" ", "+"))

    if not query_terms:
        return freq_map

    content_query = "%2C".join(query_terms)
    url = f"https://books.google.com/ngrams/json?content={content_query}&year_start=2015&year_end=2019&corpus=26&smoothing=0"

    try:
        r = requests.get(url, headers=headers, timeout=6)
        if r.status_code == 200:
            data = r.json()
            for it in data:
                ngram = it.get("ngram", "").strip()
                orig_chk = clean_map.get(ngram)
                if not orig_chk:
                    for k, v in clean_map.items():
                        if k.lower() == ngram.lower():
                            orig_chk = v
                            break
                timeseries = it.get("timeseries", [])
                if timeseries and orig_chk:
                    avg_freq = sum(timeseries) / len(timeseries)
                    freq_map[orig_chk] = avg_freq
    except Exception as e:
        logger.warning(f"Google Books Ngram query failed: {e}")

    return freq_map


def _write_promote_backup(req: PromoteChunkRequest, note_info: Dict[str, Any], cards_info: List[Dict[str, Any]]) -> Path:
    PROMOTE_BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    path = PROMOTE_BACKUP_DIR / f"{req.note_id}_{stamp}.json"
    keep = ("cardId", "deckName", "interval", "factor", "reps", "lapses", "due", "type", "queue", "left", "mod")
    payload = {
        "saved_at": stamp,
        "request": req.model_dump(),
        "note": {k: note_info.get(k) for k in ("noteId", "modelName", "tags", "fields", "cards")},
        "cards": [{k: c.get(k) for k in keep} for c in cards_info],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _collocation_model() -> str:
    # 2.5-flash(생각 켜짐) 대비 lite·생각 끔: 11.2s → 2.3s, 과금 출력 2285 → 605 토큰 (lurk 1회 측정)
    return get_setting("COLLOCATION_MODEL", "gemini-2.5-flash-lite")


def _cache_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(LLM_CACHE_PATH), timeout=5.0)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS collocations (word TEXT, model TEXT, created REAL, payload TEXT, PRIMARY KEY (word, model))"
    )
    return conn


def _cache_get(word: str, model: str) -> Optional[CollocationResponse]:
    with _cache_conn() as conn:
        row = conn.execute("SELECT created, payload FROM collocations WHERE word = ? AND model = ?", (word.lower(), model)).fetchone()
    if not row or time.time() - row[0] > COLLOCATION_CACHE_DAYS * 86400:
        return None
    res = CollocationResponse.model_validate_json(row[1])
    res.cached = True
    return res


def _cache_put(word: str, model: str, res: CollocationResponse) -> None:
    with _cache_conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO collocations (word, model, created, payload) VALUES (?, ?, ?, ?)",
            (word.lower(), model, time.time(), res.model_dump_json()),
        )


class CorpusService:
    @staticmethod
    def get_audit_stats() -> CorpusAuditStatsResponse:
        """단어 덱 16,000장 전수 빈도 감사 결과 반환"""
        if not AUDIT_JSON_PATH.exists():
            return CorpusAuditStatsResponse(
                total_notes=0,
                total_cards=0,
                tier_distribution={},
                waste_leech_count=0,
                top_waste_leeches=[]
            )
        with open(AUDIT_JSON_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return CorpusAuditStatsResponse(
            total_notes=data.get("total_notes", 0),
            total_cards=data.get("total_cards", 0),
            tier_distribution=data.get("tier_distribution", {}),
            waste_leech_count=data.get("waste_leech_count", 0),
            top_waste_leeches=data.get("waste_leeches_top50", []),
            generated_at=time.strftime("%Y-%m-%d %H:%M", time.localtime(AUDIT_JSON_PATH.stat().st_mtime)),
        )

    @staticmethod
    def get_collocations(word: str, refresh: bool = False) -> CollocationResponse:
        """
        단어에 대해 Google 1T 통계 + Google Books Ngram 빈도 검증 + Google GenAI(Gemini)를
        결합하여 100% 구글 코퍼스 통계가 검증된 네이티브 고빈도 연어/청크 후보를 생성하고 랭킹을 매겨 반환.
        """
        model = _collocation_model()
        if not refresh:
            hit = _cache_get(word, model)
            if hit is not None:
                return hit

        orig_rank, orig_tier = evaluate_expression_rank_and_tier(word)

        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY is not set.")

        # 1. Google 1T 결합 토큰 추출 (Datamuse)
        google_1t = fetch_google_1t_tokens(word)
        precs_hint = ", ".join(google_1t.get("precursors", []))
        folls_hint = ", ".join(google_1t.get("followers", []))

        hint_str = ""
        if precs_hint or folls_hint:
            hint_str = f"""
        [구글 Web 1조 단어 코퍼스 최빈도 결합 토큰 통계]:
        - 단어 앞에 가장 많이 붙는 어휘: [{precs_hint}]
        - 단어 뒤에 가장 많이 붙는 어휘: [{folls_hint}]
        위 구글 코퍼스 결합 통계를 최우선으로 반영하여 원어민들이 가장 많이 쓰는 자연스러운 덩어리 청크를 구성하세요.
            """

        client = genai.Client(api_key=api_key)

        prompt = f"""
        단어 '{word}'에 대해 영미권 원어민들이 가장 많이 쓰는 실전 고빈도 연어(Collocation) 및 관용구(Idiom) 표현 3~4개를 추천해주세요.
        {hint_str}
        [지침]:
        1. 단순 사전식 단어가 아니라, 전치사나 목적어 등이 결합된 자연스러운 덩어리 표현(Chunk)이어야 합니다. (예: beg -> beg for mercy, beg the question)
        2. 다른 동의어와의 간섭이 적고 명확한 인출 앵커가 있는 표현이어야 합니다.
        3. 각 표현에 대해 실전 예문 2개와 자연스러운 한글 번역, 그리고 뉘앙스 해설을 작성하세요.
        4. 목적어나 대상이 들어가는 자리에는 누구나 직관적으로 아는 'A', 'B' 플레이스홀더를 사용하거나, 가장 대표적인 목적어를 직접 결합하세요. (예: dispose of A, hoard supplies)
        5. 'chunk' 필드에는 괄호 설명(예: '(e.g., ...)')을 절대 포함하지 말고, 카드의 단어 표제어로 바로 쓸 수 있는 깔끔한 영문 표현만 작성하세요.
        6. 'pos' 필드에는 무조건 idiom을 쓰지 말고, 해당 청크가 문장에서 수행하는 실전 기능 품사('v', 'n', 'adj', 'adv', 'idiom' 중 하나)를 정확히 명시하세요. (예: beg for mercy -> 'v', adverse effects -> 'n', lenient with A -> 'adj', without a doubt -> 'adv')
        
        반환 형식: 아래 키를 가진 JSON 객체:
        {{
            "candidates": [
                {{
                    "chunk": "표현 (예: hoard supplies)",
                    "meaning": "한국어 뜻 (예: 물품을 사재기하다 / 비축하다)",
                    "pos": "v",
                    "example_1": "예문 1",
                    "trans_1": "예문 1 한글 번역",
                    "example_2": "예문 2",
                    "trans_2": "예문 2 한글 번역",
                    "explanation": "원어민 뉘앙스 및 쓰임새 설명"
                }}
            ]
        }}
        """

        try:
            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.2,
                    # 생각(thinking) 토큰을 끈다: 응답 품질은 비슷하고 시간·과금 출력이 크게 준다
                    thinking_config=types.ThinkingConfig(thinking_budget=0),
                )
            )
            raw_data = json.loads(response.text, strict=False)
            items = raw_data.get("candidates", [])
        except Exception as e:
            logger.error(f"Gemini collocation generation failed for '{word}': {e}")
            items = []

        raw_chunks = [it.get("chunk", "").strip() for it in items if it.get("chunk", "").strip()]
        # 2. Google Books Ngram API 배치 빈도 측정
        ngram_freqs = fetch_google_books_ngram_frequencies(raw_chunks)

        candidates: List[CollocationCandidate] = []
        for it in items:
            chk = it.get("chunk", "").strip()
            chk = re.sub(r'\(.*?\)', '', chk).strip()
            chk = re.sub(r'\s+', ' ', chk).strip()
            if not chk:
                continue
            rank, tier = evaluate_expression_rank_and_tier(chk)
            pred_pos = it.get("pos", "").strip().lower()
            if not pred_pos or pred_pos not in ['v', 'n', 'adj', 'adv', 'idiom', 'prep']:
                pred_pos = get_simple_pos(chk) or "v"

            freq_score = ngram_freqs.get(chk)

            candidates.append(CollocationCandidate(
                chunk=chk,
                meaning=it.get("meaning", "").strip(),
                pos=pred_pos,
                tier=tier,
                rank=rank,
                example_1=it.get("example_1", "").strip(),
                trans_1=it.get("trans_1", "").strip(),
                example_2=it.get("example_2", "").strip(),
                trans_2=it.get("trans_2", "").strip(),
                explanation=it.get("explanation", "").strip(),
                frequency_score=freq_score
            ))

        # Sort candidates: Google Books Ngram frequency score descending first, then word rank ascending
        candidates.sort(key=lambda x: (-(x.frequency_score or 0.0), x.rank))

        res = CollocationResponse(
            original_word=word,
            original_rank=orig_rank,
            original_tier=orig_tier,
            candidates=candidates
        )
        if candidates:
            _cache_put(word, model, res)  # 빈 결과는 저장하지 않는다
        return res

    @staticmethod
    def promote_chunk(req: PromoteChunkRequest) -> PromoteChunkResponse:
        """
        Leech 단어를 선택된 고빈도 청크로 승격시키는 원스톱 파이프라인:
        1. Anki Vocab Note 업데이트 (단어=청크, 유의어="", 예문 2개, gTTS 음성 재합성)
        2. Ease Factor 250% 복원 + 새 카드 전환(lapses=0, reps=0) + Leech 태그 제거
        3. 문장 덱(Sentence)에 예문 2개 Chirp3-HD 최고음질로 등록
        4. LinkManager 역색인 실시간 동기화
        """
        try:
            # 1. Check note existence
            notes = AnkiConnector.invoke("notesInfo", notes=[req.note_id])
            if not notes:
                return PromoteChunkResponse(
                    success=False,
                    note_id=req.note_id,
                    new_chunk=req.new_chunk,
                    error=f"Note {req.note_id} not found in Anki"
                )
            note_info = notes[0]
            card_ids = note_info.get("cards", [])

            # 1-1. 덮어쓰기·이력 초기화 전에 원본 노트와 카드 상태를 저장한다. 실패하면 중단.
            cards_info = AnkiConnector.invoke("cardsInfo", cards=card_ids) if card_ids else []
            backup_path = _write_promote_backup(req, note_info, cards_info or [])
            logger.info(f"Promote backup written: {backup_path}")

            # 2. Generate gTTS Audio for new chunk
            sound_tag, _ = AnkiTTSFiller.generate_gtts(req.new_chunk)

            # 3. Format Examples HTML
            examples_html = (
                f"1. {req.example_1}<br>"
                f"<span style=\"color:#888;font-size:0.9em;\">{req.trans_1}</span><br><br>"
                f"2. {req.example_2}<br>"
                f"<span style=\"color:#888;font-size:0.9em;\">{req.trans_2}</span>"
            )

            # 4. Update Note Fields (Strict Zero-Synonym Rule)
            update_fields = {
                "단어": req.new_chunk,
                "뜻": req.meaning,
                "품사": req.pos,
                "유의어": "",
                "예문": examples_html,
                "설명": req.explanation,
                "소리": sound_tag or ""
            }
            AnkiConnector.update_note_fields(req.note_id, update_fields)
            logger.info(f"Updated note {req.note_id} fields to chunk '{req.new_chunk}'")

            # 5. Manage Cards: Reset to New & Restore Ease Factor
            cards_reset_count = 0
            if card_ids:
                if req.reset_to_new:
                    # Reset queue and interval to New (0)
                    AnkiConnector.invoke("forgetCards", cards=card_ids)
                    for cid in card_ids:
                        AnkiConnector.invoke(
                            "setSpecificValueOfCard",
                            card=cid,
                            keys=["lapses", "reps", "due"],
                            newValues=[0, 0, 1],
                            warning_check=True
                        )
                    cards_reset_count = len(card_ids)

                # Reset Ease Factor to 2500 (250.0%)
                AnkiConnector.invoke(
                    "setEaseFactors",
                    cards=card_ids,
                    easeFactors=[2500] * len(card_ids)
                )

            # 6. Manage Tags (Remove leech/waste_leech, add new tier)
            AnkiConnector.invoke("removeTags", notes=[req.note_id], tags="leech freq::waste_leech")
            new_rank, new_tier = evaluate_expression_rank_and_tier(req.new_chunk)
            AnkiConnector.invoke("addTags", notes=[req.note_id], tags=new_tier)

            # 7. Add Example Sentences to Sentence Deck
            sentences_added_count = 0
            if req.add_sentences_to_deck:
                sentence_items = []
                if req.example_1.strip():
                    sentence_items.append(SentenceItem(
                        sentence=req.example_1.strip(),
                        translation=req.trans_1.strip()
                    ))
                if req.example_2.strip():
                    sentence_items.append(SentenceItem(
                        sentence=req.example_2.strip(),
                        translation=req.trans_2.strip()
                    ))

                if sentence_items:
                    bulk_req = SentenceBulkCreateRequest(
                        items=sentence_items,
                        generate_audio=True
                    )
                    sent_res = card_service.create_bulk_sentences(bulk_req)
                    sentences_added_count = sent_res.count
                    logger.info(f"Added {sentences_added_count} sentences to Sentence deck for chunk '{req.new_chunk}'")

            # 8. Update LinkManager
            try:
                LinkManager.index_single_vocab(req.note_id, req.new_chunk, req.meaning, req.pos)
            except Exception as link_err:
                logger.warning(f"LinkManager indexing failed for note {req.note_id}: {link_err}")

            LinkManager.invalidate_leech_cache()
            return PromoteChunkResponse(
                success=True,
                note_id=req.note_id,
                new_chunk=req.new_chunk,
                cards_reset_count=cards_reset_count,
                sentences_added_count=sentences_added_count
            )

        except Exception as e:
            logger.error(f"Failed to promote chunk for note {req.note_id}: {e}", exc_info=True)
            return PromoteChunkResponse(
                success=False,
                note_id=req.note_id,
                new_chunk=req.new_chunk,
                error=str(e)
            )
