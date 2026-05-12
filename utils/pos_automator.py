import nltk
from integrations.anki_connect import AnkiConnector
from config import MODEL_VOCAB
from utils.ui import UI

from nltk.corpus import wordnet

# NLTK 필수 데이터 다운로드
def setup_nltk():
    try:
        nltk.data.find('tokenizers/punkt')
        nltk.data.find('taggers/averaged_perceptron_tagger')
        nltk.data.find('corpora/wordnet')
    except LookupError:
        with UI.wait("NLTK 데이터를 다운로드 중입니다..."):
            nltk.download('punkt')
            nltk.download('averaged_perceptron_tagger')
            nltk.download('wordnet')
            nltk.download('omw-1.4')
            nltk.download('punkt_tab')
            nltk.download('averaged_perceptron_tagger_eng')

def get_simple_pos(word):
    """
    NLTK 품사를 사용자 친화적인 n, v, adj, adv, idiom, prep, conj로 변환
    단일 단어의 경우 WordNet을 사용해 가능한 모든 품사를 추출 (예: 'n, v')
    """
    tokens = nltk.word_tokenize(word)
    if not tokens:
        return ""
        
    # 1. 단일 단어 처리 (WordNet 사용)
    if len(tokens) == 1:
        synsets = wordnet.synsets(word)
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

    # 2. 여러 단어 처리 (기존 규칙 유지)
    tags = nltk.pos_tag(tokens)
    tag_list = [t[1] for t in tags]
    
    # 규칙 1: 모든 단어가 명사(NN) 또는 형용사(JJ)이고, 마지막이 명사(NN)로 끝나는 경우 -> n
    if all(t.startswith('NN') or t.startswith('JJ') for t in tag_list):
        if tag_list[-1].startswith('NN'):
            return 'n'
            
    # 규칙 2: 전치사(IN/TO)로 시작해서 전치사(IN/TO)로 끝나는 경우 -> prep
    if tag_list[0] in ['IN', 'TO'] and tag_list[-1] in ['IN', 'TO']:
        return 'prep'
        
    # 그 외의 모든 조합 -> idiom
    return "idiom"

def run_pos_automation():
    setup_nltk()
    
    UI.header("NLTK 품사 자동 완성")
    
    # 품사 필드가 비어있는 카드 검색
    query = f'note:"{MODEL_VOCAB}" "품사:"'
    try:
        note_ids = AnkiConnector.find_notes(query)
    except Exception as e:
        UI.error(f"Anki 연결 실패: {e}")
        return

    if not note_ids:
        UI.success("품사를 채울 카드가 없습니다. (이미 모두 채워져 있습니다)")
        return

    notes_info = AnkiConnector.get_notes_info(note_ids)
    UI.info(f"총 {len(notes_info)}개의 카드 분석 시작...")

    updated_count = 0
    
    with UI.progress() as progress:
        task = progress.add_task("[cyan]품사 분석 및 업데이트 중...", total=len(notes_info))
        
        for n in notes_info:
            note_id = n['noteId']
            word = n['fields'].get('단어', {}).get('value', '').strip()
            
            if not word:
                progress.update(task, advance=1)
                continue
                
            new_pos = get_simple_pos(word)
            
            if new_pos:
                try:
                    AnkiConnector.update_note_fields(note_id, {"품사": new_pos})
                    updated_count += 1
                except Exception as e:
                    UI.error(f"업데이트 실패 ({word}): {e}")
            
            progress.update(task, advance=1)

    UI.success(f"🎉 총 {updated_count}개의 카드에 품사가 자동으로 입력되었습니다.")

if __name__ == "__main__":
    run_pos_automation()
