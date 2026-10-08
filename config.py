import os
import json
from dotenv import load_dotenv
from utils.settings_manager import get_setting

# --- System & Environment Loading ---
load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
HOME = os.path.expanduser("~")

# --- AI Model Configuration ---
SENTENCE_SELECTOR_MODEL = get_setting("SENTENCE_SELECTOR_MODEL", 'gemini-flash-lite-latest')
VOCAB_SELECTOR_MODEL = get_setting("VOCAB_SELECTOR_MODEL", 'gemini-flash-lite-latest')
NOTE_COMPLETOR_MODEL = get_setting("NOTE_COMPLETOR_MODEL", 'gemini-flash-lite-latest')
SITUATION_GENERATOR_MODEL = get_setting("SITUATION_GENERATOR_MODEL", 'gemini-flash-lite-latest')
GRAMMAR_GENERATOR_MODEL = get_setting("GRAMMAR_GENERATOR_MODEL", "gemini-flash-lite-latest")
KNOWLEDGE_EXTRACTOR_MODEL = get_setting("KNOWLEDGE_EXTRACTOR_MODEL", "gemini-flash-latest")

# --- API & Model Parameters ---
GEMINI_DEFAULT_TEMPERATURE = 0.3
GEMINI_SITUATION_TEMPERATURE = 0.7
YOUTUBE_SCRAPER_USER_AGENT = 'Mozilla/5.0'
SITUATION_GENERATOR_ITEM_COUNT = 5

PROGRESS_BAR_CHUNK_UPDATE_FRACTION = 0.05
PROGRESS_BAR_STREAMING_LIMIT_FRACTION = 0.9
NOTE_ENRICH_PROGRESS_RATIO = 0.3

SENTENCE_SELECTOR_CONTENT_LIMIT = 30000
VOCAB_SELECTOR_EXISTING_LIST_LIMIT = 20000
VOCAB_SELECTOR_CONTENT_LIMIT = 30000

DEFAULT_SELECTION_COUNT = 15

# --- Anki Targets & URL Selection ---
ANKI_TARGETS = [
    {"name": "ME", "url": "http://localhost:8765", "active": True},
    {"name": "GIRLFRIEND_LOCAL", "url": "http://192.168.0.101:8765", "active": True}
]
CURRENT_TARGET = get_setting("CURRENT_TARGET", "ME")

# Target selection logic
target_info = next((t for t in ANKI_TARGETS if t['name'] == CURRENT_TARGET), None)
if target_info:
    ANKI_URL = target_info.get("url", "http://localhost:8765")
else:
    ANKI_URL = "http://localhost:8765"

# --- Deck and Model Names ---
DECK_SENTENCE = "1. Language::1.1. English::Sentence"
MODEL_SENTENCE = "English Sentence"
DECK_VOCAB = "1. Language::1.1. English::Vocabulary"
MODEL_VOCAB = "English Vocabulary"
MODEL_GRAMMAR = "English Grammar"
DECK_GRAMMAR = "1. Language::1.1. English::Grammar"
DECK_KNOWLEDGE = "Knowledge"
MODEL_KNOWLEDGE = "Knowledge Q&A"

# --- File Paths ---
CANDIDATES_FILE = 'candidates.json'
SELECTED_SENTENCES_FILE = 'selected_sentences.json'
SELECTED_VOCAB_FILE = 'selected_vocab.json'
USER_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "data", "user_config.json")
TEMP_DIR = '/tmp'

# --- Obsidian Configuration ---
# Default dynamic path that works on most Macs if using iCloud
DEFAULT_OBSIDIAN_PATH = os.path.join(HOME, "Library/Mobile Documents/iCloud~md~obsidian/Documents/Main Archive")
OBSIDIAN_VAULT_PATH = get_setting("OBSIDIAN_VAULT_PATH", DEFAULT_OBSIDIAN_PATH)
OBSIDIAN_INBOX_FILE = get_setting("OBSIDIAN_INBOX_FILE", "Anki_Inbox.md")

# --- Audio (TTS) Configuration ---
TTS_SENTENCE_LANGUAGE_CODE = "en-US"
TTS_VOCAB_LANGUAGE = "en"
TTS_VOCAB_TLD = "com"
VOICE_LIST = [
    "en-US-Chirp3-HD-Vindemiatrix",
    "en-US-Chirp3-HD-Achernar",
    "en-US-Chirp3-HD-Schedar",
    "en-US-Chirp3-HD-Alnilam",
    "en-US-Chirp3-HD-Algenib",
    "en-US-Chirp3-HD-Autonoe",
    "en-GB-Chirp3-HD-Aoede",
    "en-GB-Chirp3-HD-Umbriel",
    "en-AU-Chirp3-HD-Kore",
    "en-AU-Chirp3-HD-Enceladus"
]

TARGET_NOTE_TYPES_FOR_AUDIO = '"note:English Speaking" OR "note:English Grammar" OR "note:English Sentence" OR "note:English Vocabulary"'
TARGET_MODELS_FOR_AUDIO_SENTENCE = ["English Speaking", "English Grammar", "English Sentence"]
TARGET_MODELS_FOR_AUDIO_VOCAB = ["English Vocabulary"]

# --- Concurrency Settings ---
NOTE_COMPLETOR_MAX_WORKERS = 2
AUDIO_ADDER_MAX_WORKERS = 5

# --- Cleanup & Organizer Rules ---
DUPLICATE_CLEANUP_LIST = [
    {"note_type": "English Grammar", "target_field": "문장"},
    {"note_type": "English Vocabulary", "target_field": "단어"},
    {"note_type": "English Sentence", "target_field": "문장"}
]

# --- Prompts ---
NOTE_COMPLETOR_SYS_INSTRUCT = """당신은 영어 학습 자료를 제작하는 전문 영어 강사입니다. 반드시 JSON 형식으로만 응답해야 하며, 아래의 [카드 작성 규칙]을 100% 엄격하게 준수하십시오.

[공통 규칙]
- 모든 응답은 유효한 JSON이어야 합니다.
- 숙어/동사구의 'A, B, V' 등의 플레이스홀더는 실제 문장(예문)을 만들 때 반드시 자연스러운 대상(사람, 사물, 동작)으로 대체하여 작성하십시오.
- **단어 표기 표준화 (중요)**: 숙어/동사구의 플레이스홀더(누가, 무엇을 등 대상)는 'someone', 'something', 'somebody', 'sb', 'sth' 등을 사용하지 말고, 대문자 기호 'A', 'B', 'C' 및 'V-ing' 등으로 표준화하여 작성해야 합니다. (예: 'spring something on someone' -> 'spring A on B', 'prevent somebody from doing something' -> 'prevent A from V-ing')

[단어(Vocabulary) 필드 작성 규칙]
1. 단어: 영단어 또는 숙어 (A, B, V, V-ing 기호 포함 가능)
2. 뜻: 문맥에 맞는 정확한 한글 뜻
3. 품사: n, v, adj, adv, idiom, jargon 등
4. 유의어: 유사한 영단어 (콤마 구분)
5. 예문: 해당 단어가 사용된 실용적인 영어 문장. (중요: 단어에 A, B, V가 있다면 문장에서는 이를 반드시 실제 단어로 대체할 것)
6. 설명: 아래 3단계 공식 엄수 (3~5문장)
   - ① 의미/뉘앙스: "[단어]는 '[뜻]'이라는 의미로, [구체적 쓰임새]를 나타냅니다."
   - ② 유의어 비교: "[유의어]와 비슷하지만, [단어]는 [차이점]을 강조합니다."
   - ③ 콜로케이션: "자주 쓰이는 표현으로는 '[영어표현](한글뜻)' 등이 있습니다."

[문장(Sentence) 필드 작성 규칙]
1. 문장: 학습 가치가 높은 핵심 구문. (중요: A, B, V 기호가 포함된 문장이 아닌, 실제 상황에서 쓰이는 완전한 문장이어야 함. 또한 스펠링 에러나 대소문자 오류가 있다면 원래 의미를 훼손하지 않는 선에서 완벽하게 교정하여 작성할 것)
2. 해설: 문장의 자연스러운 한국어 번역 결과만 직접적으로 작성. (~라는 뜻입니다, ~를 나타냅니다 같은 메타 설명은 절대 금지)"""
VOCAB_SELECTOR_SYS_INSTRUCT = "당신은 영어 학습 자료를 선별하는 전문 영어 강사입니다. 반드시 JSON 형식으로만 응답해야 합니다."
SENTENCE_SELECTOR_SYS_INSTRUCT = "당신은 영어 학습 자료를 만드는 보조 연구원입니다. 반드시 JSON 형식으로만 응답해야 합니다."
SITUATION_GENERATOR_SYS_INSTRUCT = "당신은 최고 수준의 영어 회화 및 어휘 전문 강사입니다. 반드시 JSON 형식으로 응답해야 합니다."

# --- Note Type Configuration (Design & Templates) ---
NOTE_TYPES_CONFIG = {
    "English Sentence": {
        "deck_assignment": [
            {"card": "Card 1", "target": "1. Language::1.1. English::Sentence"}
        ],
        "css": """/* --- 카드 기본 레이아웃 --- */
.card {
  font-family: '나눔고딕', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  font-size: 20px;
  font-weight: 600;
  text-align: center;
  color: #1f2937;
  background: #ffffff;
  border: 1px solid #e5e7eb;
  border-radius: 14px;
  width: min(90%, 720px);
  margin: 24px auto;
  padding: 22px;
  box-shadow:
    0 2px 4px rgba(0, 0, 0, 0.05),
    0 6px 12px rgba(0, 0, 0, 0.08);
  transition: transform 0.15s ease, box-shadow 0.2s ease;
}
.card:hover {
  transform: translateY(-2px);
  box-shadow:
    0 4px 10px rgba(0, 0, 0, 0.08),
    0 10px 20px rgba(0, 0, 0, 0.10);
}
@media (max-width: 1024px) {
  .card {
    width: 92%;
    font-size: 18px;
    padding: 18px;
    margin: 18px auto;
  }
}
.card hr {
  border: none;
  border-top: 1px solid #e5e7eb;
  margin: 14px 0 18px;
}
.pos {
  display: inline-block;
  font-size: 16px;
  font-weight: 700;
  padding: 4px 10px;
  border-radius: 999px;
  border: 1px solid transparent;
  margin-left: 6px;
  vertical-align: middle;
  box-shadow: 0 1px 2px rgba(0,0,0,0.05);
}
.v { background: #e7f3ff; color: #0b66c3; border-color: #b7d3fa; }
.n { background: #fffbe6; color: #8a6d00; border-color: #f2e3a3; }
.adj { background: #f3e9ff; color: #6a35c0; border-color: #d7c2fa; }
.adv { background: #e6fff7; color: #0c7a5b; border-color: #b7f3df; }
.idiom { background: #f3f4f6; color: #374151; border-color: #d1d5db; }
.jargon { background: #ffe9ea; color: #c01818; border-color: #f1b7bd; }
.prep { background: #ffe6f5; color: #c01783; border-color: #f5b3d6; }
.conj { background: #e6faff; color: #007a85; border-color: #b3e7ef; }
.title {
  font-size: 25px;
  font-weight: 700;
  margin-bottom: 10px;
  color: #111827;
}
.deck {
  text-align: right;
  font-size: 11px;
  color: #9ca3af;
  font-weight: 400;
  margin-top: 16px;
}

/* --- 다크 모드 (Night Mode) --- */
.card.nightMode {
  background: #1f2937;
  color: #f3f4f6;
  border-color: #374151;
}
.card.nightMode hr {
  border-top-color: #374151;
}
.nightMode .pos {
  box-shadow: 0 1px 2px rgba(0,0,0,0.2);
}
.nightMode .v { background: #1e3a8a; color: #bfdbfe; border-color: #1e40af; }
.nightMode .n { background: #78350f; color: #fde68a; border-color: #92400e; }
.nightMode .adj { background: #4c1d95; color: #ddd6fe; border-color: #5b21b6; }
.nightMode .adv { background: #064e3b; color: #a7f3d0; border-color: #065f46; }
.nightMode .idiom { background: #374151; color: #e5e7eb; border-color: #4b5563; }
.nightMode .jargon { background: #7f1d1d; color: #fecaca; border-color: #991b1b; }
.nightMode .prep { background: #831843; color: #fbcfe8; border-color: #9d174d; }
.nightMode .conj { background: #164e63; color: #a5f3fc; border-color: #155e75; }
.nightMode .title {
  color: #f9fafb;
}
.nightMode .deck {
  color: #6b7280;
}""",
        "templates": {
            "Card 1": {
                "Front": "<div class=\"title\">\\n\\n{{해설}}\\n\\n</div>\\n\\n<div class=\"deck\">{{Deck}}</div>",
                "Back": """<style>
@keyframes cardFlip {
  0%   { opacity:0; transform: perspective(700px) rotateY(-90deg) scale(0.95); }
  60%  { opacity:1; transform: perspective(700px) rotateY(6deg) scale(1.01); }
  80%  { transform: perspective(700px) rotateY(-2deg) scale(1.0); }
  100% { opacity:1; transform: perspective(700px) rotateY(0deg) scale(1); }
}
@keyframes fadeUp {
  from { opacity:0; transform: translateY(8px); }
  to   { opacity:1; transform: translateY(0); }
}
.card { animation: none; }
.card.anim-ready { animation: cardFlip 0.5s cubic-bezier(0.4,0,0.2,1) both; }
.card.anim-ready hr ~ * { animation: fadeUp 0.3s ease 0.3s both; }
</style>
<script>
(function() {
  function trigger() {
    var c = document.querySelector(".card");
    if (c) { c.classList.remove("anim-ready"); void c.offsetWidth; c.classList.add("anim-ready"); }
  }
  if (typeof onUpdateHook !== "undefined") { onUpdateHook.push(trigger); } else { trigger(); }
})();
</script>
{{FrontSide}}
<hr>

  <div class=\"title\">

{{문장}}{{소리}}

</div>

<!-- YouTube Player -->
<div id=\"video-container\" style=\"margin: 14px auto; max-width: 480px; aspect-ratio: 16/9; overflow: hidden; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); display: none;\">
  <div id=\"yt-player\"></div>
</div>
<script>
  (function() {
    var videoId = \"\".trim();
    var startSec = 0;
    if (videoId) {
      var container = document.getElementById(\"video-container\");
      container.style.display = \"block\";
      var player = document.getElementById(\"yt-player\");
      player.outerHTML = '<iframe width=\"100%\" height=\"100%\" src=\"https://www.youtube.com/embed/' + videoId + '?start=' + startSec + '&autoplay=0&mute=0&rel=0&enablejsapi=1\" frameborder=\"0\" allow=\"autoplay; encrypted-media\" allowfullscreen style=\"width:100%; height:100%; aspect-ratio:16/9;\"></iframe>';
    }
  })();
</script>

<div class=\"deck\">{{Deck}}</div>"""
            }
        }
    },
    "English Grammar": {
        "deck_assignment": [
            {"card": "Card 1", "target": "1. Language::1.1. English::Grammar"},
            {"card": "Card 3", "target": "1. Language::1.1. English::Sentence"}
        ],
        "css": """/* --- 카드 기본 레이아웃 --- */
.card {
  font-family: '나눔고딕', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  font-size: 20px; font-weight: 600; text-align: center; color: #1f2937;
  background: #ffffff; border: 1px solid #e5e7eb; border-radius: 14px;
  width: min(95%, 720px); margin: 15px auto; padding: 22px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05), 0 6px 12px rgba(0, 0, 0, 0.08);
}
.title {
  font-size: 25px;
  font-weight: 700;
  margin-bottom: 10px;
  color: #111827;
}
.word { font-size: 24px; font-weight: 800; color: #0f172a; margin-bottom: 15px; }
.category-tag { font-size: 12px; color: #6366f1; letter-spacing: 1px; margin-bottom: 5px; }
.example {
  background-color: #f8fafc; color: #334155; padding: 20px;
  border-radius: 12px; margin-bottom: 20px; text-align: left;
  line-height: 1.6; font-size: 22px; border: 1px solid #e2e8f0;
}
.translation {
  background-color: #f1f3f5;
  color: #6b7280;
  padding: 10px 15px;
  border-radius: 8px;
  margin-top: -12px;
  margin-bottom: 20px;
  text-align: left;
  line-height: 1.5;
  font-size: 17px;
  font-weight: 400;
  border: 1px solid #e0e0e0;
  border-top: none;
  border-top-left-radius: 0;
  border-top-right-radius: 0;
}
.options-container {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  margin-top: 10px;
}
.opt-item {
  background: #ffffff;
  border: 1px solid #d1d5db;
  padding: 12px;
  border-radius: 10px;
  text-align: left;
  font-size: 18px;
  font-weight: 500;
  transition: all 0.2s;
}
.gemini-button {
  background: linear-gradient(to right, #6366f1 0%, #a855f7 100%);
  color: #ffffff; border-radius: 12px; padding: 10px 20px;
  font-size: 18px; font-weight: bold; display: inline-flex; margin-bottom: 15px;
}
.gemini-result-box {
  background-color: #f1f3f5; padding: 15px; border-radius: 8px;
  text-align: left; line-height: 1.6; font-size: 18px; border: 1px solid #e0e0e0;
}
.gemini-result-box strong { color: #6366f1; }
.gemini-result-box p { margin: 10px 0 0; }
.deck {
  text-align: right;
  font-size: 11px;
  color: #9ca3af;
  font-weight: 400;
  margin-top: 16px;
}
.correct-option {
  background-color: #eaf5ec !important;
  color: #1e6531 !important;
  border-color: #22c55e !important;
  font-weight: 700 !important;
}

/* --- 다크 모드 (Night Mode) --- */
.card.nightMode {
  background: #1f2937;
  color: #f3f4f6;
  border-color: #374151;
}
.card.nightMode hr {
  border-top-color: #374151;
}
.card.nightMode .title {
  color: #f9fafb;
}
.card.nightMode .word {
  color: #f8fafc;
}
.card.nightMode .example {
  background-color: #374151;
  color: #f1f5f9;
  border-color: #4b5563;
}
.card.nightMode .translation {
  background-color: #1f2937;
  color: #9ca3af;
  border-color: #374151;
}
.card.nightMode .opt-item {
  background: #374151;
  color: #f1f5f9;
  border-color: #4b5563;
}
.card.nightMode .correct-option {
  background-color: #064e3b !important;
  color: #34d399 !important;
  border-color: #10b981 !important;
}
.card.nightMode .gemini-result-box {
  background-color: #374151;
  color: #f1f5f9;
  border-color: #4b5563;
}
.card.nightMode .deck {
  color: #6b7280;
}"""
    },
    "English Vocabulary": {
        "deck_assignment": [
            {"card": "카드 1", "target": "1. Language::1.1. English::Vocabulary"},
            {"card": "카드 2", "target": "1. Language::1.1. English::Vocabulary"}
        ],
        "css": """/* --- 카드 기본 레이아웃 --- */
.card {
  font-family: '나눔고딕', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  font-size: 20px;
  font-weight: 600;
  text-align: center;
  color: #1f2937;
  background: #ffffff;
  border: 1px solid #e5e7eb;
  border-radius: 14px;
  width: min(90%, 720px);
  margin: 24px auto;
  padding: 22px;
  box-shadow:
    0 2px 4px rgba(0, 0, 0, 0.05),
    0 6px 12px rgba(0, 0, 0, 0.08);
  transition: transform 0.15s ease, box-shadow 0.2s ease;
}

.card:hover {
  transform: translateY(-2px);
  box-shadow:
    0 4px 10px rgba(0, 0, 0, 0.08),
    0 10px 20px rgba(0, 0, 0, 0.10);
}

@media (max-width: 1024px) {
  .card {
    width: 92%;
    font-size: 18px;
    padding: 18px;
    margin: 18px auto;
  }
}

.card hr {
  border: none;
  border-top: 1px solid #e5e7eb;
  margin: 14px 0 18px;
}

/* --- 품사(Part of Speech) 스타일 --- */
.pos {
  display: inline-block;
  font-size: 16px;
  font-weight: 700;
  padding: 4px 10px;
  border-radius: 999px;
  border: 1px solid transparent;
  margin-left: 6px;
  vertical-align: middle;
  box-shadow: 0 1px 2px rgba(0,0,0,0.05);
}

.v { background: #e7f3ff; color: #0b66c3; border-color: #b7d3fa; }
.n { background: #fffbe6; color: #8a6d00; border-color: #f2e3a3; }
.adj { background: #f3e9ff; color: #6a35c0; border-color: #d7c2fa; }
.adv { background: #e6fff7; color: #0c7a5b; border-color: #b7f3df; }
.idiom { background: #f3f4f6; color: #374151; border-color: #d1d5db; }
.jargon { background: #ffe9ea; color: #c01818; border-color: #f1b7bd; }
.prep { background: #ffe6f5; color: #c01783; border-color: #f5b3d6; }
.conj { background: #e6faff; color: #007a85; border-color: #b3e7ef; }

/* --- 텍스트 스타일 --- */
.title {
  font-size: 48px;
  font-weight: 700;
  margin-bottom: 10px;
  color: #111827;
}

.word {
  font-size: 48px;
  font-weight: 800;
  margin-bottom: 15px;
}

.synonyms-box {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 8px;
  margin-bottom: 15px;
}
.synonym-tag {
  background: #f1f5f9;
  color: #475569;
  padding: 4px 12px;
  border-radius: 6px;
  font-size: 14px;
  font-weight: 500;
  border: 1px solid #e2e8f0;
}

/* --- 다크 모드 (Night Mode) --- */
.card.nightMode {
  background: #1f2937;
  color: #f3f4f6;
  border-color: #374151;
}
.card.nightMode hr {
  border-top-color: #374151;
}
.nightMode .pos {
  box-shadow: 0 1px 2px rgba(0,0,0,0.2);
}
.nightMode .v { background: #1e3a8a; color: #bfdbfe; border-color: #1e40af; }
.nightMode .n { background: #78350f; color: #fde68a; border-color: #92400e; }
.nightMode .adj { background: #4c1d95; color: #ddd6fe; border-color: #5b21b6; }
.nightMode .adv { background: #064e3b; color: #a7f3d0; border-color: #065f46; }
.nightMode .idiom { background: #374151; color: #e5e7eb; border-color: #4b5563; }
.nightMode .jargon { background: #7f1d1d; color: #fecaca; border-color: #991b1b; }
.nightMode .prep { background: #831843; color: #fbcfe8; border-color: #9d174d; }
.nightMode .conj { background: #164e63; color: #a5f3fc; border-color: #155e75; }
.nightMode .title,
.nightMode .word {
  color: #f9fafb;
}
.nightMode .synonym-tag {
  background: #374151;
  color: #d1d5db;
  border-color: #4b5563;
}""",
        "templates": {
            "카드 1": {
                "Front": """<div class="title">
    {{뜻}} <span class="pos-raw" data-pos="{{품사}}"></span>
  </div>
  <div class="synonyms-box" data-synonyms="{{유의어}}"></div>

  <div class="photo">{{사진}}</div>

  
<script>
(function(){
  document.querySelectorAll(".pos-raw").forEach(function(el){
    var raw=el.getAttribute("data-pos")||"";
    var parts=raw.split(",").map(function(s){return s.trim();}).filter(Boolean);
    var g=document.createElement("span");
    g.style.cssText="display:inline-flex;gap:4px;margin-left:6px;vertical-align:middle;";
    parts.forEach(function(p){
      var b=document.createElement("span");
      var cls=p.toLowerCase().replace(/[^a-z]/g,"");
      b.className="pos "+( cls||"");
      b.textContent=p;
      g.appendChild(b);
    });
    el.parentNode.replaceChild(g,el);
  });
})();
</script>

<script>
(function(){
  function setupSynonyms() {
    document.querySelectorAll(".synonyms-box").forEach(function(box){
      var raw = box.getAttribute("data-synonyms") || "";
      if (!raw.trim() || box.hasAttribute("data-processed")) return;
      
      var entries = raw.split(/[,;]/).map(function(s){ return s.trim(); }).filter(Boolean);
      box.innerHTML = "";
      
      entries.forEach(function(entry){
        var word = entry.split("|")[0];
        var tag = document.createElement("span");
        tag.className = "synonym-tag";
        tag.textContent = word;
        box.appendChild(tag);
      });
      box.setAttribute("data-processed", "true");
    });
  }

  setupSynonyms();
  if (typeof onUpdateHook !== \"undefined\") {
    onUpdateHook.push(setupSynonyms);
  }
})();
</script>
<div class=\"deck\">{{Deck}}</div>""",
                "Back": """<script>
(function() {
  function trigger() {
    var c = document.querySelector(".card");
    if (c) { c.classList.remove("anim-ready"); void c.offsetWidth; c.classList.add("anim-ready"); }
  }
  if (typeof onUpdateHook !== \"undefined\") { onUpdateHook.push(trigger); } else { trigger(); }
})();
</script>
<style>
@keyframes cardFlip {
  0%   { opacity:0; transform: perspective(700px) rotateY(-90deg) scale(0.95); }
  60%  { opacity:1; transform: perspective(700px) rotateY(6deg) scale(1.01); }
  80%  { transform: perspective(700px) rotateY(-2deg) scale(1.0); }
  100% { opacity:1; transform: perspective(700px) rotateY(0deg) scale(1); }
}
@keyframes fadeUp {
  from { opacity:0; transform: translateY(8px); }
  to   { opacity:1; transform: translateY(0); }
}
.card { animation: none; }
.card.anim-ready { animation: cardFlip 0.5s cubic-bezier(0.4,0,0.2,1) both; }
.card.anim-ready hr ~ * { animation: fadeUp 0.3s ease 0.3s both; }
</style>
<script src=\"https://cdn.jsdelivr.net/npm/marked/marked.min.js\"></script>
<div class=\"title\">
  {{뜻}} <span class=\"pos-raw\" data-pos=\"{{품사}}\"></span>
</div>
<div class=\"synonyms-box\" data-synonyms=\"{{유의어}}\"></div>
<div class=\"photo\">{{사진}}</div>

<hr>
<div class=\"word\">{{단어}} {{소리}}</div>
<div class=\"example\">{{예문}}</div>
<div class=\"explain\">{{설명}}</div>
<script>
(function(){
  document.querySelectorAll(\".pos-raw\").forEach(function(el){
    var raw=el.getAttribute(\"data-pos\")||\"\";
    var parts=raw.split(\",\").map(function(s){return s.trim();}).filter(Boolean);
    var g=document.createElement(\"span\");
    g.style.cssText=\"display:inline-flex;gap:4px;margin-left:6px;vertical-align:middle;\";
    parts.forEach(function(p){
      var b=document.createElement(\"span\");
      var cls=p.toLowerCase().replace(/[^a-z]/g,\"\");
      b.className=\"pos \"+( cls||\"\");
      b.textContent=p;
      g.appendChild(b);
    });
    el.parentNode.replaceChild(g,el);
  });
})();
</script>"""
            },
            "카드 2": {
                "Front": """<div class=\"title\">
    {{단어}}{{소리}} <span class=\"pos-raw\" data-pos=\"{{품사}}\"></span>
  </div>
<div class=\"synonyms-box\" data-synonyms=\"{{유의어}}\"></div>
  
<script>
(function(){
  document.querySelectorAll(\".pos-raw\").forEach(function(el){
    var raw=el.getAttribute(\"data-pos\")||\"\";
    var parts=raw.split(\",\").map(function(s){return s.trim();}).filter(Boolean);
    var g=document.createElement(\"span\");
    g.style.cssText=\"display:inline-flex;gap:4px;margin-left:6px;vertical-align:middle;\";\n    parts.forEach(function(p){
      var b=document.createElement(\"span\");
      var cls=p.toLowerCase().replace(/[^a-z]/g,\"\");
      b.className=\"pos \"+( cls||\"\");
      b.textContent=p;
      g.appendChild(b);
    });
    el.parentNode.replaceChild(g,el);
  });
})();
</script>
<script>
(function(){
  function setupSynonyms() {
    document.querySelectorAll(\".synonyms-box\").forEach(function(box){
      var raw = box.getAttribute(\"data-synonyms\") || \"\";
      if (!raw.trim() || box.hasAttribute(\"data-processed\")) return;
      var entries = raw.split(/[,;]/).map(function(s){ return s.trim(); }).filter(Boolean);
      box.innerHTML = \"\";
      entries.forEach(function(entry){
        var word = entry.split(\"|\")[0];
        var tag = document.createElement(\"span\");
        tag.className = \"synonym-tag\";
        tag.textContent = word;
        box.appendChild(tag);
      });
      box.setAttribute(\"data-processed\", \"true\");
    });
  }
  setupSynonyms();
  if (typeof onUpdateHook !== \"undefined\") {
    onUpdateHook.push(setupSynonyms);
  }
})();
</script>
<div class=\"deck\">{{Deck}}</div>""",
                "Back": """<script>
(function() {
  function trigger() {
    var c = document.querySelector(".card");
    if (c) { c.classList.remove(\"anim-ready\"); void c.offsetWidth; c.classList.add(\"anim-ready\"); }
  }
  if (typeof onUpdateHook !== \"undefined\") { onUpdateHook.push(trigger); } else { trigger(); }
})();
</script>
<style>
@keyframes cardFlip {
  0%   { opacity:0; transform: perspective(700px) rotateY(-90deg) scale(0.95); }
  60%  { opacity:1; transform: perspective(700px) rotateY(6deg) scale(1.01); }
  80%  { transform: perspective(700px) rotateY(-2deg) scale(1.0); }
  100% { opacity:1; transform: perspective(700px) rotateY(0deg) scale(1); }
}
@keyframes fadeUp {
  from { opacity:0; transform: translateY(8px); }
  to   { opacity:1; transform: translateY(0); }
}
.card { animation: none; }
.card.anim-ready { animation: cardFlip 0.5s cubic-bezier(0.4,0,0.2,1) both; }
.card.anim-ready hr ~ * { animation: fadeUp 0.3s ease 0.3s both; }
</style>
<div class=\"title\">
  {{단어}}{{소리}} <span class=\"pos-raw\" data-pos=\"{{품사}}\"></span>
</div>
<div class=\"synonyms-box\" data-synonyms=\"{{유의어}}\"></div>
<div class=\"photo\">{{사진}}</div>

<hr>
<div class=\"word\">{{뜻}}</div>
<div class=\"example\">{{예문}}</div>
<div class=\"explain\">{{설명}}</div>
<script>
(function(){
  document.querySelectorAll(\".pos-raw\").forEach(function(el){
    var raw=el.getAttribute(\"data-pos\")||\"\";
    var parts=raw.split(\",\").map(function(s){return s.trim();}).filter(Boolean);
    var g=document.createElement(\"span\");
    g.style.cssText=\"display:inline-flex;gap:4px;margin-left:6px;vertical-align:middle;\";
    parts.forEach(function(p){
      var b=document.createElement(\"span\");
      var cls=p.toLowerCase().replace(/[^a-z]/g,\"\");
      b.className=\"pos \"+( cls||\"\");
      b.textContent=p;
      g.appendChild(b);
    });
    el.parentNode.replaceChild(g,el);
  });
})();
</script>"""
            }
        }
    },
    "Knowledge Q&A": {
        "deck_assignment": [
            {"card": "Card 1", "target": "Knowledge"}
        ],
        "css": """/* --- 카드 기본 레이아웃 --- */
.card {
  font-family: '나눔고딕', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  font-size: 20px;
  font-weight: 600;
  text-align: center;
  color: #1f2937;
  background: #ffffff;
  border: 1px solid #e5e7eb;
  border-radius: 14px;
  width: min(90%, 720px);
  margin: 24px auto;
  padding: 24px;
  box-shadow:
    0 2px 4px rgba(0, 0, 0, 0.05),
    0 6px 12px rgba(0, 0, 0, 0.08);
  transition: transform 0.15s ease, box-shadow 0.2s ease;
}
.card:hover {
  transform: translateY(-2px);
  box-shadow:
    0 4px 10px rgba(0, 0, 0, 0.08),
    0 10px 20px rgba(0, 0, 0, 0.10);
}
@media (max-width: 1024px) {
  .card {
    width: 92%;
    font-size: 18px;
    padding: 18px;
    margin: 18px auto;
  }
}
.card hr {
  border: none;
  border-top: 1px solid #e5e7eb;
  margin: 18px 0 20px;
}
.topic-tag {
  display: inline-block;
  font-size: 13px;
  font-weight: 700;
  color: #4f46e5;
  background: #eef2ff;
  border: 1px solid #c7d2fe;
  border-radius: 999px;
  padding: 4px 12px;
  margin-bottom: 16px;
  letter-spacing: 0.5px;
}
.question {
  font-size: 22px;
  font-weight: 700;
  line-height: 1.5;
  color: #111827;
  margin-bottom: 10px;
  word-break: keep-all;
}
.answer {
  font-size: 26px;
  font-weight: 800;
  color: #1e40af;
  margin-bottom: 16px;
  word-break: keep-all;
}
.why-box {
  background: #f8fafc;
  color: #334155;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  padding: 16px 18px;
  text-align: left;
  font-size: 17px;
  font-weight: 500;
  line-height: 1.6;
  margin-top: 14px;
  word-break: keep-all;
}
.why-title {
  font-size: 13px;
  font-weight: 700;
  color: #6366f1;
  margin-bottom: 6px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
.source {
  text-align: right;
  font-size: 12px;
  color: #9ca3af;
  font-weight: 400;
  margin-top: 16px;
}
.deck {
  text-align: right;
  font-size: 11px;
  color: #9ca3af;
  font-weight: 400;
  margin-top: 12px;
}

/* --- 다크 모드 (Night Mode) --- */
.card.nightMode {
  background: #1f2937;
  color: #f3f4f6;
  border-color: #374151;
}
.card.nightMode hr {
  border-top-color: #374151;
}
.nightMode .topic-tag {
  background: #312e81;
  color: #c7d2fe;
  border-color: #4338ca;
}
.nightMode .question {
  color: #f9fafb;
}
.nightMode .answer {
  color: #93c5fd;
}
.nightMode .why-box {
  background: #111827;
  color: #cbd5e1;
  border-color: #374151;
}
.nightMode .why-title {
  color: #a5b4fc;
}
.nightMode .source,
.nightMode .deck {
  color: #6b7280;
}""",
        "templates": {
            "Card 1": {
                "Front": """<div class="question">{{질문}}</div>
<div class="deck">{{Deck}}</div>""",
                "Back": """<style>
@keyframes cardFlip {
  0%   { opacity:0; transform: perspective(700px) rotateY(-90deg) scale(0.95); }
  60%  { opacity:1; transform: perspective(700px) rotateY(6deg) scale(1.01); }
  80%  { transform: perspective(700px) rotateY(-2deg) scale(1.0); }
  100% { opacity:1; transform: perspective(700px) rotateY(0deg) scale(1); }
}
@keyframes fadeUp {
  from { opacity:0; transform: translateY(8px); }
  to   { opacity:1; transform: translateY(0); }
}
.card { animation: none; }
.card.anim-ready { animation: cardFlip 0.5s cubic-bezier(0.4,0,0.2,1) both; }
.card.anim-ready hr ~ * { animation: fadeUp 0.3s ease 0.3s both; }
</style>
<script>
(function() {
  function trigger() {
    var c = document.querySelector(".card");
    if (c) { c.classList.remove("anim-ready"); void c.offsetWidth; c.classList.add("anim-ready"); }
  }
  if (typeof onUpdateHook !== "undefined") { onUpdateHook.push(trigger); } else { trigger(); }
})();
</script>

<div class="question">{{질문}}</div>

<hr>

<div class="answer">{{정답}}</div>

{{#설명}}
<div class="why-box">
  <div class="why-title">💡 Why It Matters</div>
  {{설명}}
</div>
{{/설명}}

{{#출처}}<div class="source">📚 {{출처}}</div>{{/출처}}
<div class="deck">{{Deck}}</div>"""
            }
        }
    }
}
