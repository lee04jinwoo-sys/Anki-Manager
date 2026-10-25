import os
import re
import json
import sqlite3
import html
import datetime
import functools
import logging
import time
from pathlib import Path
from collections import defaultdict
from typing import List, Dict, Any, Optional, Tuple, Set

from config import (
    DECK_VOCAB, MODEL_VOCAB, DECK_SENTENCE, MODEL_SENTENCE, MODEL_GRAMMAR,
    DECK_ZH_VOCAB, MODEL_ZH_VOCAB, DECK_ZH_SENTENCE, MODEL_ZH_SENTENCE
)
from integrations.anki_connect import AnkiConnector
from core.zh_matcher import ChineseMatcher

logger = logging.getLogger("LinkManager")

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
BACKUP_DIR = DATA_DIR / "template_backups"
DB_PATH = DATA_DIR / "links.db"

DATA_DIR.mkdir(parents=True, exist_ok=True)
BACKUP_DIR.mkdir(parents=True, exist_ok=True)


def get_db_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH), timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA busy_timeout = 5000;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    return conn


def _ensure_lang_column(cursor: sqlite3.Cursor, table: str) -> None:
    """lang 컬럼 이전에 만든 테이블에 컬럼을 붙인다. 기존 행은 모두 영어다."""
    columns = {row[1] for row in cursor.execute(f"PRAGMA table_info({table})")}
    if "lang" not in columns:
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN lang TEXT DEFAULT 'en'")


def init_db():
    """SQLite 링크 매핑 및 캐시 테이블 초기화 (WAL 모드 적용)"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("PRAGMA journal_mode = WAL;")
        cursor.execute("PRAGMA busy_timeout = 5000;")
        cursor.execute("PRAGMA synchronous = NORMAL;")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                vocab_note_id INTEGER NOT NULL,
                vocab_word TEXT NOT NULL,
                sentence_note_id INTEGER NOT NULL,
                sentence_text TEXT NOT NULL,
                lang TEXT DEFAULT 'en',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(vocab_note_id, sentence_note_id)
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_links_vocab_id ON links(vocab_note_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_links_sentence_id ON links(sentence_note_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_links_vocab_word ON links(vocab_word)")
        _ensure_lang_column(cursor, "links")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_links_lang ON links(lang)")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS vocab_cache (
                note_id INTEGER PRIMARY KEY,
                word TEXT NOT NULL,
                meaning TEXT,
                pos TEXT,
                link_count INTEGER DEFAULT 0,
                lang TEXT DEFAULT 'en',
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_vocab_link_count ON vocab_cache(link_count)")
        _ensure_lang_column(cursor, "vocab_cache")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_vocab_lang ON vocab_cache(lang)")
        conn.commit()


def clean_text(raw_html: str) -> str:
    """HTML 태그 및 특수문자 정규화"""
    if not raw_html:
        return ""
    text = html.unescape(raw_html)
    text = text.replace('‘', "'").replace('’', "'").replace('“', '"').replace('”', '"')
    text = re.sub(r'<[^>]+>', '', text)
    return text.strip()


def backup_templates() -> Optional[str]:
    """현재 Anki에 등록된 템플릿과 CSS 백업"""
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = BACKUP_DIR / f"template_backup_{timestamp}.json"
    
    backup_data: Dict[str, Any] = {
        "timestamp": timestamp,
        "models": {}
    }
    
    for model_name in [MODEL_VOCAB, MODEL_SENTENCE, MODEL_GRAMMAR]:
        try:
            templates = AnkiConnector.invoke("modelTemplates", modelName=model_name)
            styling = AnkiConnector.invoke("modelStyling", modelName=model_name)
            backup_data["models"][model_name] = {
                "templates": templates,
                "styling": styling
            }
        except Exception as e:
            backup_data["models"][model_name] = {"error": str(e)}

    with open(backup_file, "w", encoding="utf-8") as f:
        json.dump(backup_data, f, ensure_ascii=False, indent=2)
        
    return str(backup_file)


class PatternMatcher:
    """단어 및 숙어(A, B, V-ing 등 플레이스홀더 포함) 고정밀 정규식 엔진"""

    IRREGULAR_VERBS = {
        "be": r"(?:be|am|is|are|was|were|been|being|'s|'re|'m)",
        "have": r"(?:have|has|had|having|'ve|'d)",
        "do": r"(?:do|does|did|doing|done)",
        "take": r"t(?:ake|ook|aken|aking|akes)",
        "come": r"c(?:ome|ame|oming|omes)",
        "get": r"g(?:et|ot|otten|etting|ets)",
        "make": r"m(?:ake|ade|aking|akes)",
        "go": r"(?:go|went|gone|going|goes)",
        "see": r"s(?:ee|aw|een|eeing|ees)",
        "bring": r"br(?:ing|ought|inging|ings)",
        "catch": r"c(?:atch|aught|atching|atches)",
        "give": r"g(?:ive|ave|iven|iving|ives)",
        "keep": r"k(?:eep|ept|eeping|eeps)",
        "hold": r"h(?:old|eld|olding|olds)",
        "find": r"f(?:ind|ound|inding|inds)",
        "run": r"r(?:un|an|unning|uns)",
        "set": r"s(?:et|etting|ets)",
        "put": r"p(?:ut|utting|uts)",
        "tell": r"t(?:ell|old|elling|ells)",
        "say": r"s(?:ay|aid|aying|ays)",
        "leave": r"l(?:eave|eft|eaving|eaves)",
        "feel": r"f(?:eel|elt|eeling|eels)",
        "lead": r"l(?:ead|ed|eading|eads)",
        "speak": r"sp(?:eak|oke|oken|eaking|eaks)",
        "break": r"br(?:eak|oke|oken|eaking|eaks)",
        "buy": r"b(?:uy|ought|uying|uys)",
        "think": r"th(?:ink|ought|inking|inks)",
        "strike": r"str(?:ike|uck|iking|ikes)",
    }

    # 순수 기능어/전치사 (이것만으로는 숙어로 인정 X)
    PREPOSITIONS_AND_ARTICLES = {
        'of', 'in', 'on', 'at', 'to', 'for', 'with', 'by', 'from',
        'up', 'out', 'over', 'off', 'into', 'about', 'through', 'between',
        'among', 'after', 'before', 'against', 'under', 'below', 'above',
        'behind', 'beyond', 'down', 'near', 'toward', 'upon', 'onto',
        'across', 'along', 'around', 'until', 'since', 'during', 'without',
        'within', 'a', 'an', 'the', 'and', 'or', 'as', 'than', 'it'
    }

    # 너무 흔한 단일 동사 (단독+A는 99% 오매칭이므로 스킵)
    TOO_COMMON_SINGLE_VERBS = {'see', 'do', 'make', 'get', 'go', 'take', 'have', 'say', 'tell', 'know'}

    # 주어/목적어 대명사 및 명사구 패턴
    NOUN_PHRASE_PATTERN = r"(?:(?:i|you|he|she|it|we|they|me|him|her|us|them)|(?:the\s+|a\s+|an\s+|my\s+|your\s+|his\s+|her\s+|our\s+|their\s+)?[\w'-]+(?:\s+[\w'-]+){0,2})"

    # 개별 부사 단어 목록 (빈출 부사 및 강조어)
    ADVERB_TOKEN = r"(?:way|far|really|so|much|well|still|just|quite|completely|totally|fairly|already|never|always|definitely|certainly|not|n't|almost|hardly|barely|scarcely|more|less|too|even)"

    # 선택적 부사 수식어 (0~2단어 연속 결합 허용: e.g., 'always so', 'really quite', 'still way', 'far more')
    OPTIONAL_ADVERB = rf"(?:\s+{ADVERB_TOKEN}(?:\s+{ADVERB_TOKEN})?)?"

    @classmethod
    def verb_to_regex(cls, token: str) -> str:
        low = token.lower()
        if low in cls.IRREGULAR_VERBS:
            return cls.IRREGULAR_VERBS[low]
        if low.endswith('e') and len(low) > 2:
            base = low[:-1]
            return rf"{re.escape(base)}(?:e|ed|es|ing)"
        if low.endswith('y') and len(low) > 2:
            base = low[:-1]
            return rf"(?:{re.escape(base)}(?:y|ies|ied|ying)|{re.escape(low)})"
        return rf"{re.escape(low)}(?:s|ed|es|ing)?"

    INDEX_PREFIX_LEN = 3

    @classmethod
    def index_key(cls, token: str) -> str:
        """역색인 키: 앞 3글자. 변화형(accommodated, carried, loved)도 원형과 같은 키를 갖는다."""
        return token[:cls.INDEX_PREFIX_LEN]

    @classmethod
    def get_index_keywords(cls, cleaned_text: str) -> List[str]:
        """
        역색인 사전 필터용 키워드(앞 3글자) 추출. 최종 판정은 build_regex가 한다.
        - 불규칙 동사(take/took, run/ran)는 접두어가 바뀌므로 키에서 뺀다.
        - 전치사·관사·be/have/do, 플레이스홀더, '/' 대안 표기, 괄호 안 내용은 뺀다.
        - 키가 하나도 없으면 빈 리스트 → 호출부가 전체 문장을 정규식으로 검사한다.
        """
        text = re.sub(r'\(.*?\)', '', cleaned_text).lower()
        keys = []
        for t in text.split():
            if '/' in t or t.upper() in ('A', 'B', 'C', 'V', 'V-ING', 'V_ING'):
                continue
            t_clean = re.sub(r"[^\w'-]", '', t)
            if len(t_clean) < 2 or t_clean in cls.IRREGULAR_VERBS:
                continue
            if t_clean in cls.PREPOSITIONS_AND_ARTICLES or t_clean in ('be', 'have', 'do'):
                continue
            keys.append(cls.index_key(t_clean))
        return keys

    @classmethod
    def build_regex(cls, word_or_idiom: str) -> Optional[re.Pattern]:
        """단어/숙어용 정규식. 단어별로 한 번만 만든다 (re 모듈 자체 캐시는 512개뿐)."""
        return _cached_build_regex(word_or_idiom)

    @classmethod
    def clear_regex_cache(cls) -> None:
        _cached_build_regex.cache_clear()

    @classmethod
    def _build_regex_uncached(cls, word_or_idiom: str) -> Optional[re.Pattern]:
        cleaned = clean_text(word_or_idiom).strip()
        if not cleaned:
            return None

        cleaned = re.sub(r'\(.*?\)', '', cleaned).strip()
        tokens = cleaned.split()
        if not tokens:
            return None

        upper_tokens = [t.upper() for t in tokens]
        has_placeholder = any(t in ('A', 'B', 'C', 'V', 'V-ING', 'V_ING') for t in upper_tokens)

        # 플레이스홀더를 제외한 실제 단어들
        non_placeholder_tokens = [
            re.sub(r"[^\w'-]", '', t).lower()
            for t in tokens
            if t.upper() not in ('A', 'B', 'C', 'V', 'V-ING', 'V_ING')
        ]
        non_placeholder_tokens = [t for t in non_placeholder_tokens if t]

        # [특이도 필터 1] 플레이스홀더 포함 숙어인데 의미어가 하나도 없거나 전부 전치사/관사뿐인 경우 스킵!
        # 예: 'A over B', 'A out of B' -> 100% false positive 폭탄이므로 스킵
        if has_placeholder:
            if not non_placeholder_tokens:
                return None
            if all(t in cls.PREPOSITIONS_AND_ARTICLES for t in non_placeholder_tokens):
                return None
            # 예: 'see A' 처럼 단일 초빈출 동사 1개뿐인 경우 스킵
            if len(non_placeholder_tokens) == 1 and non_placeholder_tokens[0] in cls.TOO_COMMON_SINGLE_VERBS:
                return None

        # [특수 케이스] 'many a A' -> 고정 관용구이므로 'many a [단어]' 엄격 매칭
        if len(tokens) == 3 and tokens[0].lower() == 'many' and tokens[1].lower() == 'a' and upper_tokens[2] == 'A':
            return re.compile(r"\bmany\s+a\s+[a-zA-Z]+(?:\s+[a-zA-Z]+){0,2}\b", re.IGNORECASE)

        pattern_parts = []
        for i, token in enumerate(tokens):
            t_upper = token.upper()
            if t_upper in ('A', 'B', 'C'):
                pattern_parts.append(cls.NOUN_PHRASE_PATTERN)
            elif t_upper in ('V-ING', 'V_ING'):
                pattern_parts.append(r"[a-zA-Z'-]+ing")
            elif t_upper == 'V':
                pattern_parts.append(r"[a-zA-Z'-]+")
            elif '/' in token:
                sub_parts = [re.escape(p) for p in token.split('/') if p]
                pattern_parts.append(rf"(?:{'|'.join(sub_parts)})")
            else:
                token_clean = re.sub(r"[^\w'-]", '', token).lower()
                if not token_clean:
                    continue

                if token_clean in cls.IRREGULAR_VERBS:
                    v_regex = cls.IRREGULAR_VERBS[token_clean]
                    # be 동사나 일반 동사 뒤에 선택적 부사 허용
                    if token_clean == 'be':
                        pattern_parts.append(rf"(?:{v_regex}){cls.OPTIONAL_ADVERB}")
                    else:
                        pattern_parts.append(v_regex)
                elif i == 0 and len(tokens) > 1:
                    pattern_parts.append(cls.verb_to_regex(token_clean))
                elif len(tokens) == 1:
                    pattern_parts.append(cls.verb_to_regex(token_clean))
                else:
                    pattern_parts.append(re.escape(token_clean))

        # be 동사 축약형('s) 허용: 주어 바로 뒤에 's가 붙는 경우 (he's, it's 등)
        # 공백 또는 따옴표 축약 결합 허용
        regex_str = r"\b" + r"(?:\s+|(?=[']))".join(pattern_parts) + r"\b"
        try:
            return re.compile(regex_str, re.IGNORECASE)
        except re.error:
            return re.compile(r"\b" + re.escape(cleaned.lower()) + r"\b", re.IGNORECASE)


@functools.lru_cache(maxsize=32768)
def _cached_build_regex(word_or_idiom: str) -> Optional[re.Pattern]:
    return PatternMatcher._build_regex_uncached(word_or_idiom)


# Leech 목록: 페이지 넘김·검색마다 카드 2천여 장의 cardsInfo를 다시 받지 않도록 잠깐 재사용한다.
_LEECH_CACHE_TTL = 60.0
_leech_cache: Dict[str, Tuple[float, List[Dict[str, Any]]]] = {}


class LinkManager:
    """초고속 역색인 기반 단어-문장 링크 관리 서비스"""

    @classmethod
    def invalidate_leech_cache(cls) -> None:
        _leech_cache.clear()

    @classmethod
    def scan_and_rebuild_links(cls, lang: str = "en") -> Dict[str, Any]:
        init_db()

        # 배치 로드 헬퍼
        def fetch_in_chunks(ids: List[int], chunk_size: int = 2000):
            res = []
            for i in range(0, len(ids), chunk_size):
                chunk = ids[i:i + chunk_size]
                info = AnkiConnector.get_notes_info(chunk)
                if info:
                    res.extend(info)
            return res

        if lang == "zh":
            vocab_notes_ids = AnkiConnector.find_notes(f'note:"{MODEL_ZH_VOCAB}"') or []
            sentence_notes_ids = AnkiConnector.find_notes(f'note:"{MODEL_ZH_SENTENCE}"') or []

            vocab_info_list = fetch_in_chunks(vocab_notes_ids)
            sentence_info_list = fetch_in_chunks(sentence_notes_ids)

            sentences_dict: Dict[int, str] = {}
            for s in sentence_info_list:
                nid = s['noteId']
                stext = clean_text(s['fields'].get('문장', {}).get('value', ''))
                if stext:
                    sentences_dict[nid] = stext

            vocabs = []
            for v in vocab_info_list:
                nid = v['noteId']
                word_raw = v['fields'].get('단어', {}).get('value', '')
                word = clean_text(word_raw)
                meaning = clean_text(v['fields'].get('뜻', {}).get('value', ''))
                pos = clean_text(v['fields'].get('품사', {}).get('value', ''))
                if word:
                    vocabs.append({
                        "note_id": nid,
                        "word": word,
                        "meaning": meaning,
                        "pos": pos,
                    })

            links_to_insert = []
            vocab_counts: Dict[int, int] = {v["note_id"]: 0 for v in vocabs}
            matcher = ChineseMatcher(v["word"] for v in vocabs)
            sentence_tokens = {s_id: matcher.tokens(s_text) for s_id, s_text in sentences_dict.items()}

            for v in vocabs:
                for s_id, s_text in sentences_dict.items():
                    if matcher.contains(v["word"], sentence_tokens[s_id]):
                        links_to_insert.append((v["note_id"], v["word"], s_id, s_text))
                        vocab_counts[v["note_id"]] += 1

            cls.invalidate_leech_cache()
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM links WHERE lang = ?", (lang,))
                cursor.execute("DELETE FROM vocab_cache WHERE lang = ?", (lang,))

                cursor.executemany("""
                    INSERT OR IGNORE INTO links (vocab_note_id, vocab_word, sentence_note_id, sentence_text, lang)
                    VALUES (?, ?, ?, ?, ?)
                """, [(l[0], l[1], l[2], l[3], lang) for l in links_to_insert])

                vocab_cache_data = [
                    (v["note_id"], v["word"], v["meaning"], v["pos"], vocab_counts.get(v["note_id"], 0), lang)
                    for v in vocabs
                ]
                cursor.executemany("""
                    INSERT INTO vocab_cache (note_id, word, meaning, pos, link_count, lang)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, vocab_cache_data)

                conn.commit()

            return {
                "total_vocab": len(vocabs),
                "total_sentences": len(sentences_dict),
                "total_links": len(links_to_insert),
                "unlinked_vocab_count": sum(1 for c in vocab_counts.values() if c == 0)
            }

        # 기본 영어(en) 스캔 로직
        vocab_notes_ids = AnkiConnector.find_notes(f'note:"{MODEL_VOCAB}"') or []
        sentence_notes_ids = AnkiConnector.find_notes(f'note:"{MODEL_SENTENCE}" OR note:"{MODEL_GRAMMAR}"') or []

        vocab_info_list = fetch_in_chunks(vocab_notes_ids)
        sentence_info_list = fetch_in_chunks(sentence_notes_ids)

        # 2. 문장 데이터 구조화 및 고속 역색인(Inverted Index) 구축
        sentences_dict: Dict[int, str] = {}
        inverted_index: Dict[str, Set[int]] = defaultdict(set)

        for s in sentence_info_list:
            nid = s['noteId']
            stext = clean_text(s['fields'].get('문장', {}).get('value', ''))
            if stext:
                sentences_dict[nid] = stext
                # 문장 단어 토큰화
                tokens = re.findall(r"\b[a-zA-Z'-]+\b", stext.lower())
                for t in tokens:
                    inverted_index[PatternMatcher.index_key(t)].add(nid)

        # 3. 단어 데이터 정제 및 정규식 컴파일
        vocabs = []
        for v in vocab_info_list:
            nid = v['noteId']
            word_raw = v['fields'].get('단어', {}).get('value', '')
            word = clean_text(word_raw)
            meaning = clean_text(v['fields'].get('뜻', {}).get('value', ''))
            pos = clean_text(v['fields'].get('품사', {}).get('value', ''))
            if word:
                regex = PatternMatcher.build_regex(word)
                keywords = PatternMatcher.get_index_keywords(word)
                vocabs.append({
                    "note_id": nid,
                    "word": word,
                    "meaning": meaning,
                    "pos": pos,
                    "regex": regex,
                    "keywords": keywords
                })

        # 4. 초고속 역색인 기반 매칭 (O(N*M) -> O(N * 후보군))
        links_to_insert = []
        vocab_counts: Dict[int, int] = {v["note_id"]: 0 for v in vocabs}

        for v in vocabs:
            regex = v["regex"]
            if not regex:
                continue

            keywords = v["keywords"]
            if keywords:
                # 모든 키워드(앞 3글자)를 가진 문장만 후보로 남긴다. 하나라도 없으면 후보 없음.
                candidate_sids: Set[int] = set(inverted_index.get(keywords[0], ()))
                for kw in keywords[1:]:
                    if not candidate_sids:
                        break
                    candidate_sids &= inverted_index.get(kw, set())
            else:
                # 불규칙 동사·기능어로만 된 표현은 사전 필터 없이 전체 문장을 정규식으로 검사
                candidate_sids = set(sentences_dict)
            if not candidate_sids:
                continue

            # 극소수의 후보 문장들에 대해서만 정규식 정밀 검사
            for s_id in candidate_sids:
                s_text = sentences_dict.get(s_id, '')
                if s_text and regex.search(s_text):
                    links_to_insert.append((v["note_id"], v["word"], s_id, s_text))
                    vocab_counts[v["note_id"]] += 1

        # 5. DB 일괄 저장
        cls.invalidate_leech_cache()
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM links WHERE lang = ?", (lang,))
            cursor.execute("DELETE FROM vocab_cache WHERE lang = ?", (lang,))

            cursor.executemany("""
                INSERT OR IGNORE INTO links (vocab_note_id, vocab_word, sentence_note_id, sentence_text, lang)
                VALUES (?, ?, ?, ?, ?)
            """, [(l[0], l[1], l[2], l[3], lang) for l in links_to_insert])

            vocab_cache_data = [
                (v["note_id"], v["word"], v["meaning"], v["pos"], vocab_counts.get(v["note_id"], 0), lang)
                for v in vocabs
            ]
            cursor.executemany("""
                INSERT INTO vocab_cache (note_id, word, meaning, pos, link_count, lang)
                VALUES (?, ?, ?, ?, ?, ?)
            """, vocab_cache_data)

            conn.commit()

        return {
            "total_vocab": len(vocabs),
            "total_sentences": len(sentences_dict),
            "total_links": len(links_to_insert),
            "unlinked_vocab_count": sum(1 for c in vocab_counts.values() if c == 0)
        }

    @classmethod
    def get_stats(cls, lang: str = "en") -> Dict[str, Any]:
        init_db()
        target_vocab_model = MODEL_ZH_VOCAB if lang == "zh" else MODEL_VOCAB
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM vocab_cache WHERE lang = ?", (lang,))
            total_vocab = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(DISTINCT sentence_note_id) FROM links WHERE lang = ?", (lang,))
            linked_sentences = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM links WHERE lang = ?", (lang,))
            total_links = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM vocab_cache WHERE link_count = 0 AND lang = ?", (lang,))
            unlinked_vocab = cursor.fetchone()[0]

            leech_count = 0
            try:
                # 단어(노트) 단위: 카드가 2장인 단어를 두 번 세지 않는다
                if lang == "zh":
                    leech_q = f'note:"{target_vocab_model}" -is:new (prop:ease<=1.3 OR prop:lapses>=4) -is:suspended'
                else:
                    leech_q = f'note:"{target_vocab_model}" -is:new (prop:ease<=1.3 OR prop:lapses>=4) -is:suspended -tag:freq::tier4_academic -tag:freq::tier5_rare'

                leech_notes = AnkiConnector.invoke("findNotes", query=leech_q) or []
                from backend.services import leech_history
                treated = leech_history.get_all()
                pending = [n for n in leech_notes if n in treated]
                if pending:
                    notes = AnkiConnector.invoke("notesInfo", notes=pending) or []
                    card_ids = [c for n in notes if n for c in n.get("cards", [])]
                    max_lapses: Dict[int, int] = {}
                    for c in AnkiConnector.invoke("cardsInfo", cards=card_ids) or []:
                        max_lapses[c["note"]] = max(max_lapses.get(c["note"], 0), c.get("lapses", 0))
                    hidden = {n for n in pending if not leech_history.status(treated[n], max_lapses.get(n, 0))["relapsed"]}
                    leech_notes = [n for n in leech_notes if n not in hidden]
                leech_count = len(leech_notes)
            except Exception:
                pass

            return {
                "total_vocab": total_vocab,
                "total_links": total_links,
                "linked_sentences": linked_sentences,
                "unlinked_vocab": unlinked_vocab,
                "leech_count": leech_count
            }

    @classmethod
    def get_vocab_list(
        cls,
        limit: int = 50,
        offset: int = 0,
        filter_mode: Optional[str] = None,
        max_links: Optional[int] = None,
        search: Optional[str] = None,
        lang: str = "en"
    ) -> Dict[str, Any]:
        init_db()
        target_vocab_model = MODEL_ZH_VOCAB if lang == "zh" else MODEL_VOCAB

        if filter_mode == "treated":
            return cls._treated_list(limit, offset, search, lang=lang)

        # Handle leech filter mode
        if filter_mode == "leech":
            try:
                if lang == "zh":
                    anki_q = f'note:"{target_vocab_model}" -is:new (prop:ease<=1.3 OR prop:lapses>=4) -is:suspended'
                else:
                    anki_q = f'note:"{target_vocab_model}" -is:new (prop:ease<=1.3 OR prop:lapses>=4) -is:suspended -tag:freq::tier4_academic -tag:freq::tier5_rare'

                if search:
                    anki_q += f' "{search}"'
                cached = _leech_cache.get(anki_q)
                if cached and time.time() - cached[0] < _LEECH_CACHE_TTL:
                    ranked = cached[1]
                else:
                    card_ids = AnkiConnector.invoke("findCards", query=anki_q) or []
                    all_cards = AnkiConnector.invoke("cardsInfo", cards=card_ids) if card_ids else []

                    worst_by_note: Dict[int, Dict[str, Any]] = {}
                    for c in all_cards or []:
                        nid = c["note"]
                        prev = worst_by_note.get(nid)
                        if prev is None or (c.get("lapses", 0), -c.get("factor", 0)) > (prev.get("lapses", 0), -prev.get("factor", 0)):
                            worst_by_note[nid] = c
                    ranked = sorted(worst_by_note.values(), key=lambda c: (-c.get("lapses", 0), c.get("factor", 0)))
                    _leech_cache[anki_q] = (time.time(), ranked)

                from backend.services import leech_history
                treated = leech_history.get_all()
                treated_status: Dict[int, Dict[str, Any]] = {}
                visible = []
                for c in ranked:
                    row = treated.get(c["note"])
                    if row is None:
                        visible.append(c)
                        continue
                    st = leech_history.status(row, c.get("lapses", 0))
                    if st["relapsed"]:
                        treated_status[c["note"]] = st
                        visible.append(c)
                ranked = visible
                total_items = len(ranked)
                cards_info = ranked[offset:offset + limit]
                note_ids = [c["note"] for c in cards_info]

                with get_db_connection() as conn:
                    cursor = conn.cursor()
                    placeholders = ','.join('?' * len(note_ids)) if note_ids else '0'
                    cursor.execute(
                        f"SELECT note_id, word, meaning, pos, link_count FROM vocab_cache WHERE note_id IN ({placeholders}) AND lang = ?",
                        [*note_ids, lang] if note_ids else [lang]
                    )
                    cache_map = {row["note_id"]: dict(row) for row in cursor.fetchall()}

                items = []
                for c in cards_info:
                    nid = c["note"]
                    cached = cache_map.get(nid, {})
                    fields = c.get("fields", {})
                    word = cached.get("word") or fields.get("단어", {}).get("value", "")
                    meaning = cached.get("meaning") or fields.get("뜻", {}).get("value", "")
                    pos = cached.get("pos") or fields.get("품사", {}).get("value", "")
                    link_cnt = cached.get("link_count", 0)
                    ease_val = round(c.get("factor", 1300) / 10.0, 1)

                    items.append({
                        "treated": treated_status.get(nid),
                        "note_id": nid,
                        "card_id": c.get("cardId"),
                        "word": clean_text(word),
                        "meaning": clean_text(meaning),
                        "pos": pos,
                        "link_count": link_cnt,
                        "lapses": c.get("lapses", 0),
                        "ease": ease_val,
                        "reps": c.get("reps", 0)
                    })

                return {
                    "total": total_items,
                    "limit": limit,
                    "offset": offset,
                    "items": items
                }
            except Exception as e:
                pass

        with get_db_connection() as conn:
            cursor = conn.cursor()

            query = "SELECT note_id, word, meaning, pos, link_count FROM vocab_cache WHERE lang = ?"
            params: List[Any] = [lang]

            if filter_mode == "zero" or max_links == 0:
                query += " AND link_count = 0"
            elif filter_mode == "low" or max_links == 1:
                query += " AND link_count <= 1"
            elif max_links is not None:
                query += " AND link_count <= ?"
                params.append(max_links)

            if search:
                query += " AND (word LIKE ? OR meaning LIKE ?)"
                params.extend([f"%{search}%", f"%{search}%"])

            count_query = f"SELECT COUNT(*) FROM ({query})"
            cursor.execute(count_query, params)
            total_items = cursor.fetchone()[0]

            query += " ORDER BY link_count ASC, word ASC LIMIT ? OFFSET ?"
            params.extend([limit, offset])

            cursor.execute(query, params)
            items = [dict(row) for row in cursor.fetchall()]

            return {
                "total": total_items,
                "limit": limit,
                "offset": offset,
                "items": items
            }

    @classmethod
    def _treated_list(cls, limit: int, offset: int, search: Optional[str], lang: str = "en") -> Dict[str, Any]:
        """처리한 단어 목록: 처리 방법·시각과 처리 후 오답 수 (최근 처리 순)."""
        from backend.services import leech_history
        rows = sorted(leech_history.get_all().values(), key=lambda r: -r["treated_at"])
        if search:
            rows = [r for r in rows if search.lower() in (r.get("word") or "").lower()]
        page = rows[offset:offset + limit]
        note_ids = [r["note_id"] for r in page]
        notes = {n["noteId"]: n for n in (AnkiConnector.invoke("notesInfo", notes=note_ids) if note_ids else []) or [] if n}
        card_ids = [c for n in notes.values() for c in n.get("cards", [])]
        cards = AnkiConnector.invoke("cardsInfo", cards=card_ids) if card_ids else []
        max_lapses: Dict[int, int] = {}
        for c in cards or []:
            max_lapses[c["note"]] = max(max_lapses.get(c["note"], 0), c.get("lapses", 0))
        with get_db_connection() as conn:
            placeholders = ",".join("?" * len(note_ids)) or "0"
            cache = {r["note_id"]: dict(r) for r in conn.execute(
                f"SELECT note_id, word, meaning, pos, link_count FROM vocab_cache WHERE note_id IN ({placeholders}) AND lang = ?",
                [*note_ids, lang] if note_ids else [lang])}
        items = []
        for r in page:
            nid = r["note_id"]
            fields = notes.get(nid, {}).get("fields", {})
            cached = cache.get(nid, {})
            lapses = max_lapses.get(nid, 0)
            items.append({
                "note_id": nid,
                "word": clean_text(fields.get("단어", {}).get("value", "")) or r.get("word", ""),
                "meaning": clean_text(fields.get("뜻", {}).get("value", "")) or cached.get("meaning", ""),
                "pos": clean_text(fields.get("품사", {}).get("value", "")) or cached.get("pos", ""),
                "link_count": cached.get("link_count", 0),
                "lapses": lapses,
                "treated": leech_history.status(r, lapses),
            })
        return {"total": len(rows), "limit": limit, "offset": offset, "items": items}

    @classmethod
    def get_linked_sentences_for_vocab(cls, word: str, lang: str = "en") -> List[Dict[str, Any]]:
        init_db()
        cleaned_word = clean_text(word).strip()
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT sentence_note_id, sentence_text
                FROM links
                WHERE lower(vocab_word) = lower(?) AND lang = ?
            """, (cleaned_word, lang))
            return [dict(row) for row in cursor.fetchall()]

    @classmethod
    def get_linked_vocab_for_sentence(cls, sentence_text: str, lang: str = "en") -> List[Dict[str, Any]]:
        init_db()
        cleaned = clean_text(sentence_text).strip()
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT DISTINCT l.vocab_word, v.meaning, v.pos
                FROM links l
                LEFT JOIN vocab_cache v ON l.vocab_note_id = v.note_id AND v.lang = ?
                WHERE lower(l.sentence_text) = lower(?) AND l.lang = ?
            """, (lang, cleaned, lang))
            rows = cursor.fetchall()
            return [
                {
                    "word": row["vocab_word"],
                    "meaning": row["meaning"] or "",
                    "pos": row["pos"] or ""
                }
                for row in rows
            ]

    @classmethod
    def get_random_unlinked_vocab(cls, count: int = 20, lang: str = "en") -> List[Dict[str, Any]]:
        """미연결(link_count = 0) 단어 중 무작위 N개 추출"""
        init_db()
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT note_id, word, meaning, pos, link_count
                FROM vocab_cache
                WHERE link_count = 0 AND lang = ?
                ORDER BY RANDOM()
                LIMIT ?
            """, (lang, count))
            return [dict(row) for row in cursor.fetchall()]

    @classmethod
    def get_worst_leech_unlinked_vocab(cls, count: int = 20, lang: str = "en") -> List[Dict[str, Any]]:
        """미연결(link_count = 0) 단어 중 가장 많이 틀린(Lapses 많은 순) 단어 N개 추출"""
        init_db()
        from integrations.anki_connect import AnkiConnector
        target_vocab_model = MODEL_ZH_VOCAB if lang == "zh" else MODEL_VOCAB

        card_lapses = {}
        try:
            if lang == "zh":
                leech_q = f'note:"{target_vocab_model}" prop:lapses>=3'
            else:
                leech_q = f'note:"{target_vocab_model}" prop:lapses>=3 -tag:freq::tier4_academic -tag:freq::tier5_rare'

            leech_cards = AnkiConnector.invoke('findCards', query=leech_q)
            if leech_cards:
                for c in AnkiConnector.invoke('cardsInfo', cards=leech_cards) or []:
                    card_lapses[c['note']] = max(card_lapses.get(c['note'], 0), c.get('lapses', 0))
        except Exception:
            card_lapses = {}

        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT note_id, word, meaning, pos, link_count
                FROM vocab_cache
                WHERE link_count = 0 AND lang = ?
            """, (lang,))
            zero_items = [dict(row) for row in cursor.fetchall()]

        matched = []
        for item in zero_items:
            nid = item['note_id']
            item['lapses'] = card_lapses.get(nid, 0)
            if item['lapses'] > 0:
                matched.append(item)

        matched.sort(key=lambda x: -x['lapses'])
        return matched[:count]

    @classmethod
    def index_single_sentence(cls, sentence_note_id: int, sentence_text: str, lang: str = "en"):
        """새로 생성된 단일 문장을 vocab_cache와 대조하여 즉시 links.db에 증분 반영"""
        init_db()
        cleaned_sentence = clean_text(sentence_text).strip()
        if not cleaned_sentence:
            return

        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT note_id, word FROM vocab_cache WHERE lang = ?", (lang,))
            vocabs = cursor.fetchall()

            links_to_add = []
            vocab_ids_to_increment = set()

            if lang == "zh":
                matcher = ChineseMatcher(row["word"] for row in vocabs)
                tokens = matcher.tokens(cleaned_sentence)
                for row in vocabs:
                    v_id = row["note_id"]
                    v_word = row["word"]
                    if matcher.contains(v_word, tokens):
                        links_to_add.append((v_id, v_word, sentence_note_id, cleaned_sentence, lang))
                        vocab_ids_to_increment.add(v_id)
            else:
                for row in vocabs:
                    v_id = row["note_id"]
                    v_word = row["word"]
                    regex = PatternMatcher.build_regex(v_word)
                    if regex and regex.search(cleaned_sentence):
                        links_to_add.append((v_id, v_word, sentence_note_id, cleaned_sentence, lang))
                        vocab_ids_to_increment.add(v_id)

            if links_to_add:
                cursor.executemany("""
                    INSERT OR IGNORE INTO links (vocab_note_id, vocab_word, sentence_note_id, sentence_text, lang)
                    VALUES (?, ?, ?, ?, ?)
                """, links_to_add)
                for v_id in vocab_ids_to_increment:
                    cursor.execute("UPDATE vocab_cache SET link_count = link_count + 1 WHERE note_id = ? AND lang = ?", (v_id, lang))
                conn.commit()

                # 단어 카드의 '예문' 필드에 최대 5개 한도로 자동 덧붙임 (토큰 0개)
                for v_id in vocab_ids_to_increment:
                    try:
                        cls._append_sentence_to_vocab_note(v_id, cleaned_sentence)
                    except Exception as e:
                        pass

    @classmethod
    def _append_sentence_to_vocab_note(cls, vocab_note_id: int, new_sentence: str):
        """단어 카드의 '예문' 필드에 새 문장을 최대 5개 한도 내에서 |||로 자동 덧붙임 (로컬 연산, 토큰 0개)"""
        clean_new = clean_text(new_sentence).strip()
        if not clean_new:
            return

        notes_info = AnkiConnector.get_notes_info([vocab_note_id])
        if not notes_info or not notes_info[0]:
            return

        fields = notes_info[0].get("fields", {})
        curr_ex = fields.get("예문", {}).get("value", "").strip()

        parts = [p.strip() for p in curr_ex.split("|||") if p.strip()]
        if len(parts) >= 5:
            return

        for existing in parts:
            if clean_text(existing).lower() == clean_new.lower():
                return

        parts.append(clean_new)
        new_val = " ||| ".join(parts)
        AnkiConnector.update_note_fields(vocab_note_id, {"예문": new_val})

    @classmethod
    def remove_note(cls, note_id: int) -> None:
        """지운 노트를 색인에서 뺀다 (/undo). 문장이면 등록 때 단어 카드 '예문'에 덧붙인 그 문장도 되돌린다."""
        init_db()
        with get_db_connection() as conn:
            cursor = conn.cursor()
            rows = cursor.execute(
                "SELECT vocab_note_id, sentence_text FROM links WHERE sentence_note_id = ?", (note_id,)
            ).fetchall()
            for row in rows:
                try:
                    cls._remove_sentence_from_vocab_note(row["vocab_note_id"], row["sentence_text"])
                except Exception as e:
                    logger.warning(f"예문 되돌리기 실패 (vocab {row['vocab_note_id']}): {e}")
                cursor.execute(
                    "UPDATE vocab_cache SET link_count = MAX(link_count - 1, 0) WHERE note_id = ?",
                    (row["vocab_note_id"],),
                )
            cursor.execute("DELETE FROM links WHERE sentence_note_id = ?", (note_id,))
            cursor.execute("DELETE FROM links WHERE vocab_note_id = ?", (note_id,))
            cursor.execute("DELETE FROM vocab_cache WHERE note_id = ?", (note_id,))
            conn.commit()

    @classmethod
    def _remove_sentence_from_vocab_note(cls, vocab_note_id: int, sentence: str) -> None:
        target = clean_text(sentence).strip().lower()
        notes_info = AnkiConnector.get_notes_info([vocab_note_id])
        if not target or not notes_info or not notes_info[0]:
            return
        curr = notes_info[0].get("fields", {}).get("예문", {}).get("value", "")
        parts = [p.strip() for p in curr.split("|||") if p.strip()]
        kept = [p for p in parts if clean_text(p).strip().lower() != target]
        if len(kept) != len(parts):
            AnkiConnector.update_note_fields(vocab_note_id, {"예문": " ||| ".join(kept)})

    @classmethod
    def index_single_vocab(cls, vocab_note_id: int, vocab_word: str, meaning: str = "", pos: str = ""):
        """새로 생성된 단일 어휘를 vocab_cache 및 기존 문장들과 즉시 매칭하여 증분 반영"""
        init_db()
        cleaned_word = clean_text(vocab_word).strip()
        if not cleaned_word:
            return

        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO vocab_cache (note_id, word, meaning, pos, link_count)
                VALUES (?, ?, ?, ?, (SELECT COALESCE(COUNT(*), 0) FROM links WHERE vocab_note_id = ?))
            """, (vocab_note_id, cleaned_word, clean_text(meaning), clean_text(pos), vocab_note_id))

            regex = PatternMatcher.build_regex(cleaned_word)
            if regex:
                cursor.execute("SELECT DISTINCT sentence_note_id, sentence_text FROM links")
                existing_sentences = cursor.fetchall()
                links_to_add = []
                for s_row in existing_sentences:
                    s_id = s_row["sentence_note_id"]
                    s_text = s_row["sentence_text"]
                    if regex.search(s_text):
                        links_to_add.append((vocab_note_id, cleaned_word, s_id, s_text))
                if links_to_add:
                    cursor.executemany("""
                        INSERT OR IGNORE INTO links (vocab_note_id, vocab_word, sentence_note_id, sentence_text)
                        VALUES (?, ?, ?, ?)
                    """, links_to_add)
                    cursor.execute("""
                        UPDATE vocab_cache 
                        SET link_count = (SELECT COUNT(*) FROM links WHERE vocab_note_id = ?) 
                        WHERE note_id = ?
                    """, (vocab_note_id, vocab_note_id))
            conn.commit()

