import logging
import nltk
from integrations.anki_connect import AnkiConnector
from config import MODEL_VOCAB

from nltk.corpus import wordnet

logger = logging.getLogger("PosAutomator")

# NLTK 필수 데이터: (리소스 경로, 다운로드 패키지명)
_NLTK_RESOURCES = [
    ("tokenizers/punkt", "punkt"),
    ("tokenizers/punkt_tab", "punkt_tab"),
    ("taggers/averaged_perceptron_tagger", "averaged_perceptron_tagger"),
    ("taggers/averaged_perceptron_tagger_eng", "averaged_perceptron_tagger_eng"),
    ("corpora/wordnet", "wordnet"),
    ("corpora/omw-1.4", "omw-1.4"),
]


def _nltk_has(resource: str) -> bool:
    # 코퍼스는 zip으로만 설치되기도 한다 (corpora/wordnet.zip). nltk는 zip을 그대로 읽는다.
    for name in (resource, resource + ".zip"):
        try:
            nltk.data.find(name)
            return True
        except LookupError:
            continue
    return False


def setup_nltk():
    """없는 리소스만 내려받는다."""
    for resource, package in _NLTK_RESOURCES:
        if not _nltk_has(resource):
            logger.info(f"NLTK 데이터 다운로드: {package}")
            nltk.download(package, quiet=True)

def get_simple_pos(word: str) -> str:
    """
    NLTK 품사를 사용자 친화적인 n, v, adj, adv, idiom, prep, conj로 변환
    단일 단어의 경우 WordNet을 사용해 가능한 모든 품사를 추출 (예: 'n, v')
    청크/연어의 경우 실전 기능 품사 체계('v', 'n', 'adj', 'adv', 'prep', 'idiom')로 정밀 분류
    """
    import html
    import re

    cleaned = html.unescape(word or "")
    cleaned = re.sub(r'<[^>]+>', ' ', cleaned)
    cleaned = re.sub(r'&[a-zA-Z]+;', ' ', cleaned).strip()

    tokens = nltk.word_tokenize(cleaned)
    if not tokens:
        return ""
        
    # 1. 단일 단어 처리 (WordNet 사용)
    if len(tokens) == 1:
        synsets = wordnet.synsets(cleaned)
        if not synsets:
            # WordNet에 없으면 기본 태거 사용
            tag = nltk.pos_tag(tokens)[0][1]
            if tag.startswith('NN'): return 'n'
            if tag.startswith('VB'): return 'v'
            if tag.startswith('JJ'): return 'adj'
            if tag.startswith('RB'): return 'adv'
            if tag in ['IN', 'TO']: return 'prep'
            if tag == 'CC': return 'conj'
            return 'etc'
            
        # 가능한 모든 품사 수집
        pos_set = set()
        for syn in synsets:
            p = syn.pos()
            if p == 'n': pos_set.add('n')
            elif p in ['v']: pos_set.add('v')
            elif p in ['a', 's']: pos_set.add('adj')
            elif p == 'r': pos_set.add('adv')
            
        if not pos_set:
            return 'etc'
            
        # 사용자 취향에 맞게 정렬 (n, v 순서 등)
        priority = {'n': 1, 'v': 2, 'adj': 3, 'adv': 4}
        sorted_pos = sorted(list(pos_set), key=lambda x: priority.get(x, 9))
        return ", ".join(sorted_pos)

    # 2. 여러 단어 처리 (실전 기능 품사 체계: v, n, adj, adv, prep, idiom)
    raw_tokens = [t for t in tokens if t.isalnum()]
    if not raw_tokens:
        return "idiom"

    first_raw = raw_tokens[0].lower()
    last_raw = raw_tokens[-1].lower()

    PREP_HEADS = {
        'in', 'on', 'at', 'by', 'for', 'with', 'without', 'under', 'beyond', 'over', 'from',
        'as', 'out', 'to', 'except', 'apart', 'aside', 'instead', 'because', 'due', 'owing',
        'prior', 'thanks', 'regardless', 'inasmuch', 'up'
    }
    CLOSING_PREPS = {'of', 'to', 'for', 'with', 'in', 'on', 'about', 'from', 'as', 'into'}

    NON_PARTICIPLE_ING = {'bring', 'sing', 'ring', 'spring', 'cling', 'fling', 'sling', 'string', 'swing', 'wring', 'king', 'wing', 'thing'}
    NON_PARTICIPLE_ED = {'bed', 'feed', 'bleed', 'breed', 'speed', 'seed', 'weed', 'need', 'shed', 'red'}

    def is_participle(tok: str) -> bool:
        t = tok.lower()
        if t.endswith('ing') and len(t) > 4 and t not in NON_PARTICIPLE_ING:
            return True
        if t.endswith('ed') and len(t) > 4 and t not in NON_PARTICIPLE_ED:
            return True
        return False

    # 규칙 1: 관사 (a, an, the)
    if first_raw in ['a', 'an', 'the']:
        is_placeholder_a = (len(raw_tokens) >= 2 and raw_tokens[1].lower() in ['be', 'have', 'do', 'is', 'are', 'prior'])
        if not is_placeholder_a:
            if last_raw in CLOSING_PREPS:
                return 'prep'
            return 'n'

    # 플레이스홀더 필터링 (A be attributed to B -> be attributed to B)
    placeholders = {'a', 'b', 'c', 'sb', 'sth', 'someone', 'something', 'x', 'y', 'one'}
    content_tokens = [t for t in raw_tokens if t.lower() not in placeholders and not t.lower().endswith("'s")]
    if not content_tokens:
        content_tokens = raw_tokens

    first = content_tokens[0].lower()
    last = content_tokens[-1].lower()

    # 규칙 2: 복합 전치사구 및 부사구
    if first in PREP_HEADS:
        if last in CLOSING_PREPS:
            return 'prep'
        return 'adv'

    # 규칙 3: Be + 형용사/구문 -> v
    if first == 'be':
        return 'v'

    # 규칙 4: 순수 형용사 + 전치사 결합 청크 (adept at, fastidious about, lenient with, terrified of) -> adj
    if len(content_tokens) >= 2:
        second = content_tokens[1].lower()
        if second in CLOSING_PREPS or second in ['at', 'about']:
            v_syn = wordnet.synsets(first, pos=wordnet.VERB)
            adj_syn = wordnet.synsets(first, pos=wordnet.ADJ)
            if adj_syn and (not v_syn or is_participle(first)):
                return 'adj'

    # 규칙 5: 첫 단어가 동사인 실전 동사구 (beg for mercy, live in exile, bring about A, cope with)
    blacklist_verbs = {
        'state', 'point', 'power', 'room', 'question', 'statue', 'adverse',
        'unquestionably', 'sensational', 'conscientious', 'capricious', 'esoteric',
        'steadfast', 'frivolous', 'compelling', 'plenty', 'lack', 'kind', 'sort'
    }
    v_synsets = wordnet.synsets(first, pos=wordnet.VERB)
    if v_synsets and first not in blacklist_verbs and not is_participle(first):
        return 'v'

    # 규칙 6: Noun + of/for/in + A (statue of A, lack of A)
    if len(content_tokens) >= 2 and content_tokens[1].lower() in ['of', 'for', 'in', 'to'] and wordnet.synsets(first, pos=wordnet.NOUN):
        if last in CLOSING_PREPS:
            return 'prep'
        return 'n'

    # 규칙 7: 태거 기반 말미 어휘 판별
    tags = nltk.pos_tag(content_tokens)
    tag_list = [t[1] for t in tags]

    if tag_list[-1].startswith('JJ') or (len(content_tokens) >= 2 and tag_list[0].startswith('RB') and wordnet.synsets(last, pos=wordnet.ADJ)):
        return 'adj'

    if wordnet.synsets(last, pos=wordnet.NOUN) or tag_list[-1].startswith('NN'):
        return 'n'

    # 그 외 비유적 관용구 -> idiom
    return "idiom"

def run_pos_automation() -> int:
    setup_nltk()
    logger.info("NLTK 품사 자동 완성 시작")
    
    # 품사 필드가 비어있는 카드 검색
    query = f'note:"{MODEL_VOCAB}" "품사:"'
    try:
        note_ids = AnkiConnector.find_notes(query)
    except Exception as e:
        logger.error(f"Anki 연결 실패: {e}")
        return 0

    if not note_ids:
        logger.info("품사를 채울 카드가 없습니다. (이미 모두 채워져 있습니다)")
        return 0

    notes_info = AnkiConnector.get_notes_info(note_ids)
    logger.info(f"총 {len(notes_info)}개의 카드 분석 시작...")

    updated_count = 0
    for n in notes_info:
        note_id = n['noteId']
        word = n['fields'].get('단어', {}).get('value', '').strip()
        
        if not word:
            continue
            
        new_pos = get_simple_pos(word)
        
        if new_pos:
            try:
                AnkiConnector.update_note_fields(note_id, {"품사": new_pos})
                updated_count += 1
            except Exception as e:
                logger.error(f"업데이트 실패 ({word}): {e}")

    logger.info(f"총 {updated_count}개의 카드에 품사가 자동으로 입력되었습니다.")
    return updated_count

if __name__ == "__main__":
    run_pos_automation()
