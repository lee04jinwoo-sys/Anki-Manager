# Anki/Anki Manager/config.py

# --- AI Model Configuration ---
SENTENCE_SELECTOR_MODEL = 'gemini-1.5-flash'
VOCAB_SELECTOR_MODEL = 'gemini-1.5-flash'
NOTE_COMPLETOR_MODEL = 'gemini-1.5-pro'
SITUATION_GENERATOR_MODEL = 'gemini-1.5-flash'

# --- API & Model Parameters ---
GEMINI_DEFAULT_TEMPERATURE = 0.3
GEMINI_SITUATION_TEMPERATURE = 0.7
YOUTUBE_SCRAPER_USER_AGENT = 'Mozilla/5.0'

# --- System & Path Configuration ---
ANKI_URL = "http://localhost:8765"
CANDIDATES_FILE = 'candidates.json'
SELECTED_SENTENCES_FILE = 'selected_sentences.json'
SELECTED_VOCAB_FILE = 'selected_vocab.json'
TEMP_DIR = '/tmp'

# --- Anki Deck and Model Names ---
DECK_SENTENCE = "1. Language::1.1. English::Sentence"
MODEL_SENTENCE = "English Sentence"
DECK_VOCAB = "1. Language::1.1. English::Vocabulary"
MODEL_VOCAB = "English Vocabulary"
TARGET_NOTE_TYPES_FOR_AUDIO = '"note:English Speaking" OR "note:English Grammar" OR "note:English Vocabulary" OR "note:English Sentence"'
TARGET_MODELS_FOR_AUDIO_SENTENCE = ["English Speaking", "English Grammar", "English Sentence"]
TARGET_MODELS_FOR_AUDIO_VOCAB = ["English Vocabulary"]

# --- Audio Generation (TTS) Configuration ---
TTS_SENTENCE_LANGUAGE_CODE = "en-US"
TTS_VOCAB_LANGUAGE = "en"
TTS_VOCAB_TLD = "com"
VOICE_LIST = [
    # 🇺🇸 미국 영어 (기본 회화 및 리스닝)
    "en-US-Studio-O",     # 여성 (차분하고 명확한 톤)
    "en-US-Studio-M",      # 남성 (안정적인 중저음)
    "en-US-Wavenet-F",      # 여성 (밝은 일상 대화톤)
    "en-US-Wavenet-D", # 남성 (친근하고 부드러운 톤)
]
# --- Concurrency Settings ---
NOTE_COMPLETOR_MAX_WORKERS = 2
AUDIO_ADDER_MAX_WORKERS = 5

# --- Prompts ---
NOTE_COMPLETOR_SYS_INSTRUCT = """당신은 TOEFL 100점 이상의 중급 영어 학습자를 지도하는 꼼꼼하고 전문적인 영어 강사입니다.
반드시 JSON 형식으로만 응답해야 하며, 아래의 [카드 작성 규칙]과 [예시]의 문체, 설명 깊이, 문장 구조를 100% 완벽하게 모방하십시오.

[단어 필드 작성 규칙]
1. 단어: 영단어 또는 숙어 
   *중요 규칙: 목적어나 보어가 동반되는 숙어 및 동사의 경우, 명사 자리는 'A', 'B'로 표기하고, 동사 원형은 'V', 동명사는 'V-ing'로 명확히 구조화하십시오. (예: consist of A, consider V-ing)
2. 뜻: 문맥에 맞는 정확한 한글 뜻 (2개 이상 시 콤마로 구분). 
   *중요 규칙: 영어 단어에 쓰인 A, B, V, V-ing 기호를 한글 뜻에도 동일하게 매칭하십시오. (예: 'A로 구성되다', 'V하는 것을 고려하다')
   *중요 규칙: 단어가 특정 문체를 가질 경우 뜻 옆에 '(격식)', '(문예)', '(비격식)' 등의 태그를 반드시 기재하십시오.
3. 품사: n, v, adj, adv, idiom, jargon 중 택일 (2개 이상 시 'n, v' 형태로 작성)
4. 유의어: 의미가 유사한 영단어 1~4개 (콤마로 구분, 없을 경우 빈 문자열)
5. 예문: 해당 단어가 사용된 실용적이고 자연스러운 영어 문장
6. 설명: 아래 3단계 공식에 맞춰 반드시 3~5문장으로 서술할 것.
   - ① 의미 및 뉘앙스 정의: "[단어]는 '[뜻]'이라는 뜻으로/의미하며, [구체적인 뉘앙스/쓰임새]를 나타냅니다." 
     *주의: 품사가 2개 이상이거나, V-ing를 목적어로 취하는 등의 문법적 특징이 있다면 반드시 서술할 것.
   - ② 유의어 비교: "'[유의어/관련 단어]'와 유사하지만/관련되지만, [단어]는 [어떤 미묘한 차이나 강도, 쓰임새의 차이]를 의미/강조합니다."
   - ③ 콜로케이션(연어) 마무리: 마지막 문장은 반드시 "자주 쓰이는 표현으로는 '[영어표현](한글뜻)' 등이 있습니다." 또는 "'[영어표현](한글뜻)'과 같이 사용/쓰입니다." 로 끝낼 것.

   [단어 생성 예시 (이 톤과 문장 구조를 무조건 따를 것)]
{
  "단어": "contract",
  "뜻": "계약, 계약서, 수축하다",
  "품사": "n, v",
  "유의어": "agreement",
  "예문": "The contract had been validly drawn up.",
  "설명": "contract는 '계약'이라는 명사 외에 '수축하다, 계약하다'라는 동사로도 쓰입니다. 명사로서의 계약은 법적 구속력을 가지는 합의를 의미하며, 동사로서의 수축은 물리적인 크기가 줄어드는 것을 의미합니다. 'agreement'와 유사하지만, contract는 법적 효력이 있는 문서화된 합의를 강조합니다. 'sign a contract(계약서에 서명하다)'와 같이 사용됩니다."
}

[문장 필드 작성 규칙]
1. 문장: 학습 가치가 높은, 원어민이 자주 쓰는 핵심 구문
2. 해설: 문장의 자연스러운 한국어 번역
"""

VOCAB_SELECTOR_SYS_INSTRUCT = "당신은 영어 학습 자료를 선별하는 전문 영어 강사입니다. 반드시 JSON 형식으로만 응답해야 합니다."
VOCAB_SELECTOR_EXISTING_LIST_LIMIT = 1000
VOCAB_SELECTOR_CONTENT_LIMIT = 40000

SENTENCE_SELECTOR_SYS_INSTRUCT = "당신은 영어 학습 자료를 만드는 보조 연구원입니다. 반드시 JSON 형식으로만 응답해야 합니다."
SENTENCE_SELECTOR_CONTENT_LIMIT = 40000

SITUATION_GENERATOR_SYS_INSTRUCT = "당신은 최고 수준의 영어 회화 및 어휘 전문 강사입니다. 반드시 JSON 형식으로 응답해야 합니다."
SITUATION_GENERATOR_ITEM_COUNT = 20

# --- Workflow Manager Configuration ---
WORKFLOW_STEPS = {
    "콘텐츠 추출": {"points": 10},
    "문장 선별": {"points": 30},
    "어휘 선별": {"points": 20},
    "노트 추가": {"points": 20},
    "음성 추가": {"points": 15},
    "카드 정리": {"points": 5},
}
PROGRESS_BAR_CHUNK_UPDATE_FRACTION = 0.05
PROGRESS_BAR_STREAMING_LIMIT_FRACTION = 0.9
NOTE_ENRICH_PROGRESS_RATIO = 0.3

# --- Card Organizer Rules ---
ORGANIZER_RULES = [
    {
        "query": '"note:English Vocabulary"', 
        "target_deck": "1. Language::1.1. English::Vocabulary"
    },
    {
        "query": '"note:English Sentence" "card:Card 1"', 
        "target_deck": "1. Language::1.1. English::Sentence"
    },
    {
        "query": '"note:English Sentence" "card:Card 2"', 
        "target_deck": "1. Language::1.1. English::listening"
    },
    {
        "query": '"note:English Grammar" "card:Card 1"', 
        "target_deck": "1. Language::1.1. English::Grammar"
    },
    {
        "query": '"note:English Grammar" "card:Card 2"', 
        "target_deck": "1. Language::1.1. English::listening"
    },
    {
        "query": '"note:English Grammar" "card:Card 3"', 
        "target_deck": "1. Language::1.1. English::Sentence"
    }
]
