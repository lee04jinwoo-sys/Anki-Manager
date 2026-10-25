"""
Unify Chinese Card Design & Styling with English Design System.
Exact 1:1 match with English Vocabulary and English Sentence layouts.
Includes robust cloze masking (exact match priority + separable verb + correlative conjunction support),
refined typography for Chinese Hanzi (PingFang SC) and Pinyin (Avenir Next / Lucida Grande),
English POS abbreviations (v, n, adj, etc.), and official HSK difficulty badges for Vocabulary.
Sentence cards have a super clean layout with NO badges or difficulty tags (text + audio + pinyin only).
"""

import json
import os
import sys
from pathlib import Path

os.environ["no_proxy"] = "*"
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from integrations.anki_connect import AnkiConnector

MODEL_ZH_VOCAB = "Chinese Vocabulary"
MODEL_ZH_SENTENCE = "Chinese Sentence"

# ==============================================================================
# 1. CHINESE VOCABULARY CSS
# ==============================================================================
CHINESE_VOCAB_CSS = r"""/* --- LXGW WenKai GB (霞鹜文楷) 서체 선언 (한자 전용 unicode-range 적용) --- */
@font-face {
  font-family: "LXGW WenKai GB";
  src: local("LXGW WenKai GB"), local("霞鹜文楷 GB"), url("_LXGWWenKaiGB-Regular.ttf");
  font-weight: 400;
  font-style: normal;
  unicode-range: U+4E00-9FFF, U+3400-4DBF, U+20000-2A6DF, U+F900-FAFF, U+2E80-2EFF, U+3000-303F, U+FF00-FFEF;
}
@font-face {
  font-family: "LXGW WenKai GB";
  src: local("LXGW WenKai GB Medium"), local("霞鹜文楷 GB Medium"), url("_LXGWWenKaiGB-Medium.ttf");
  font-weight: 500;
  font-style: normal;
  unicode-range: U+4E00-9FFF, U+3400-4DBF, U+20000-2A6DF, U+F900-FAFF, U+2E80-2EFF, U+3000-303F, U+FF00-FFEF;
}
@font-face {
  font-family: "LXGW WenKai GB";
  src: local("LXGW WenKai GB Medium"), local("霞鹜文楷 GB Medium"), local("LXGW WenKai GB Bold"), url("_LXGWWenKaiGB-Medium.ttf");
  font-weight: 600;
  font-style: normal;
  unicode-range: U+4E00-9FFF, U+3400-4DBF, U+20000-2A6DF, U+F900-FAFF, U+2E80-2EFF, U+3000-303F, U+FF00-FFEF;
}
@font-face {
  font-family: "LXGW WenKai GB";
  src: local("LXGW WenKai GB Medium"), local("霞鹜文楷 GB Medium"), local("LXGW WenKai GB Bold"), url("_LXGWWenKaiGB-Medium.ttf");
  font-weight: 700;
  font-style: normal;
  unicode-range: U+4E00-9FFF, U+3400-4DBF, U+20000-2A6DF, U+F900-FAFF, U+2E80-2EFF, U+3000-303F, U+FF00-FFEF;
}

/* --- 카드 기본 레이아웃: 한자는 LXGW WenKai GB, 한글은 영어 카드와 동일한 나눔고딕 --- */
.card {
  font-family: "LXGW WenKai GB", '나눔고딕', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
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
  box-sizing: border-box;
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

/* --- 품사(Part of Speech) 스타일 (영문 약어 적용) --- */
.pos {
  display: inline-block;
  font-size: 15px;
  font-weight: 700;
  padding: 3px 9px;
  border-radius: 999px;
  border: 1px solid transparent;
  vertical-align: middle;
  box-shadow: 0 1px 2px rgba(0,0,0,0.04);
}

.v { background: #e7f3ff; color: #0b66c3; border-color: #b7d3fa; }
.n { background: #fffbe6; color: #8a6d00; border-color: #f2e3a3; }
.adj { background: #f3e9ff; color: #6a35c0; border-color: #d7c2fa; }
.adv { background: #e6fff7; color: #0c7a5b; border-color: #b7f3df; }
.pron { background: #fef3c7; color: #b45309; border-color: #fde68a; }
.num { background: #ffedd5; color: #c2410c; border-color: #fed7aa; }
.mw { background: #ecfdf5; color: #047857; border-color: #a7f3d0; }
.prep { background: #ffe6f5; color: #c01783; border-color: #f5b3d6; }
.conj { background: #e6faff; color: #007a85; border-color: #b3e7ef; }
.aux { background: #f0fdf4; color: #15803d; border-color: #bbf7d0; }
.part { background: #f1f5f9; color: #475569; border-color: #cbd5e1; }
.idiom { background: #f3f4f6; color: #374151; border-color: #d1d5db; }

/* --- 난이도/HSK 뱃지 스타일 --- */
.tier-badge {
  display: inline-block;
  font-size: 13px;
  font-weight: 700;
  padding: 3px 9px;
  border-radius: 999px;
  border: 1px solid transparent;
  vertical-align: middle;
  box-shadow: 0 1px 2px rgba(0,0,0,0.04);
}
.tier-1 { background: #eff6ff; color: #1d4ed8; border-color: #bfdbfe; }
.tier-2 { background: #f0f9ff; color: #0369a1; border-color: #bae6fd; }
.tier-3 { background: #eef2ff; color: #4338ca; border-color: #c7d2fe; }
.tier-4 { background: #fff7ed; color: #c2410c; border-color: #fed7aa; }
.tier-5 { background: #f8fafc; color: #475569; border-color: #cbd5e1; }
.tier-6 { background: #f3f4f6; color: #374151; border-color: #d1d5db; }

/* --- 텍스트 스타일 --- */
.title {
  font-size: 28px;
  font-weight: 600;
  margin-bottom: 10px;
  color: #111827;
  word-break: keep-all;
}

.word {
  font-size: 28px;
  font-weight: 600;
  margin-bottom: 15px;
  color: #111827;
}

/* 한어병음 전용 타이포그래피 (Avenir Next, Lucida Grande - 성조 기호 최적화) */
.pinyin {
  font-family: "Avenir Next", "Lucida Grande", "Helvetica Neue", -apple-system, sans-serif;
  font-size: 19px;
  font-weight: 500;
  color: #4b5563;
  letter-spacing: 0.035em;
  margin: -2px 0 14px;
  font-feature-settings: "liga" 1;
}

.photo { margin: 12px 0; }
.photo img { max-width: 100%; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
.deck { font-size: 14px; font-weight: 400; color: #9ca3af; text-align: right; margin-top: 6px; }

/* --- 예문 컨테이너 박스 (한자는 LXGW WenKai GB, 한글 해석은 나눔고딕) --- */
.example {
  background-color: #f1f3f5;
  color: #1f2937;
  padding: 16px 18px;
  border-radius: 10px;
  margin-top: 16px;
  text-align: left;
  line-height: 1.6;
  font-size: 20px;
  border: 1px solid #e0e0e0;
  box-shadow: inset 0 1px 3px rgba(0,0,0,0.04);
}

.example .pinyin-sub {
  font-family: '나눔고딕', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  font-size: 15px;
  font-weight: 400;
  color: #64748b;
  margin-top: 8px;
  line-height: 1.5;
  letter-spacing: 0.025em;
  display: block;
}

/* --- Cloze Blank --- */
.example .cloze-blank {
  display: inline-block;
  font-family: "SF Pro Rounded", "SF Mono", Menlo, Consolas, -apple-system, monospace;
  font-weight: 700;
  color: #0071e3;
  letter-spacing: 0.15em;
  padding: 0 4px;
  vertical-align: baseline;
}

/* --- Example Highlight --- */
.example-highlight {
  color: #0071e3;
  font-weight: 600;
  text-decoration: underline;
  text-decoration-color: #0071e3;
  text-underline-offset: 4px;
}

/* --- 플립 애니메이션 --- */
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

/* --- 다크모드 대응 --- */
@media (prefers-color-scheme: dark) {
  .card { background: #191919; color: #e3e3e3; border-color: #2f2f2f; }
  .title, .word { color: #f3f4f6; }
  .pinyin { color: #9ca3af; }
  .example { background: #1e1e1e; color: #cfcfcf; border-color: #2f2f2f; }
  .example .pinyin-sub { color: #94a3b8; }
  .example .cloze-blank { color: #38bdf8; }
  .example-highlight { color: #38bdf8; text-decoration-color: #38bdf8; }
  .v { background: #1a2a3a; color: #8ab4f8; border-color: #2a4060; }
  .n { background: #2a2500; color: #e8c84a; border-color: #4a3e00; }
  .adj { background: #251a3a; color: #c09af0; border-color: #3d2a60; }
  .adv { background: #0e2a20; color: #6dcfad; border-color: #1a4a35; }
  .pron { background: #78350f; color: #fde68a; border-color: #92400e; }
  .num { background: #7c2d12; color: #fed7aa; border-color: #9a3412; }
  .mw { background: #064e3b; color: #a7f3d0; border-color: #065f46; }
  .tier-1 { background: #1e3a8a; color: #bfdbfe; border-color: #1e40af; }
  .tier-2 { background: #0c4a6e; color: #7dd3fc; border-color: #0369a1; }
  .tier-3 { background: #312e81; color: #c7d2fe; border-color: #4338ca; }
  .tier-4 { background: #7c2d12; color: #fed7aa; border-color: #9a3412; }
  .tier-5 { background: #334155; color: #cbd5e1; border-color: #475569; }
  .tier-6 { background: #1f2937; color: #9ca3af; border-color: #374151; }
}

.card.nightMode { background: #1f2937; color: #f3f4f6; border-color: #374151; }
.card.nightMode hr { border-top-color: #374151; }
.card.nightMode .title, .card.nightMode .word { color: #f9fafb; }
.card.nightMode .pinyin { color: #9ca3af; }
.card.nightMode .example { background-color: #374151; color: #f1f5f9; border-color: #4b5563; }
.card.nightMode .example .pinyin-sub { color: #94a3b8; }
.card.nightMode .cloze-blank { color: #38bdf8; }
.card.nightMode .example-highlight { color: #38bdf8; text-decoration-color: #38bdf8; }
.card.nightMode .v { background: #1e3a8a; color: #bfdbfe; border-color: #1e40af; }
.card.nightMode .n { background: #78350f; color: #fde68a; border-color: #92400e; }
.card.nightMode .adj { background: #4c1d95; color: #ddd6fe; border-color: #5b21b6; }
.card.nightMode .adv { background: #064e3b; color: #a7f3d0; border-color: #065f46; }
"""

# ==============================================================================
# 2. CHINESE SENTENCE CSS (Super clean: NO badges!)
# ==============================================================================
CHINESE_SENTENCE_CSS = r"""/* --- LXGW WenKai GB (霞鹜文楷) 서체 선언 (한자 전용 unicode-range 적용) --- */
@font-face {
  font-family: "LXGW WenKai GB";
  src: local("LXGW WenKai GB"), local("霞鹜文楷 GB"), url("_LXGWWenKaiGB-Regular.ttf");
  font-weight: 400;
  font-style: normal;
  unicode-range: U+4E00-9FFF, U+3400-4DBF, U+20000-2A6DF, U+F900-FAFF, U+2E80-2EFF, U+3000-303F, U+FF00-FFEF;
}
@font-face {
  font-family: "LXGW WenKai GB";
  src: local("LXGW WenKai GB Medium"), local("霞鹜文楷 GB Medium"), url("_LXGWWenKaiGB-Medium.ttf");
  font-weight: 500;
  font-style: normal;
  unicode-range: U+4E00-9FFF, U+3400-4DBF, U+20000-2A6DF, U+F900-FAFF, U+2E80-2EFF, U+3000-303F, U+FF00-FFEF;
}
@font-face {
  font-family: "LXGW WenKai GB";
  src: local("LXGW WenKai GB Medium"), local("霞鹜文楷 GB Medium"), local("LXGW WenKai GB Bold"), url("_LXGWWenKaiGB-Medium.ttf");
  font-weight: 600;
  font-style: normal;
  unicode-range: U+4E00-9FFF, U+3400-4DBF, U+20000-2A6DF, U+F900-FAFF, U+2E80-2EFF, U+3000-303F, U+FF00-FFEF;
}
@font-face {
  font-family: "LXGW WenKai GB";
  src: local("LXGW WenKai GB Medium"), local("霞鹜文楷 GB Medium"), local("LXGW WenKai GB Bold"), url("_LXGWWenKaiGB-Medium.ttf");
  font-weight: 700;
  font-style: normal;
  unicode-range: U+4E00-9FFF, U+3400-4DBF, U+20000-2A6DF, U+F900-FAFF, U+2E80-2EFF, U+3000-303F, U+FF00-FFEF;
}

/* --- 카드 기본 레이아웃: 한자는 LXGW WenKai GB, 한글은 영어 카드와 동일한 나눔고딕 --- */
.card {
  font-family: "LXGW WenKai GB", '나눔고딕', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
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
  box-sizing: border-box;
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

.title {
  font-size: 25px;
  font-weight: 600;
  margin-bottom: 10px;
  color: #111827;
  line-height: 1.5;
  word-break: keep-all;
}

/* 중국어 문장 전용 타이포그래피 (LXGW WenKai GB 1순위) */
.zh-sentence {
  font-family: "LXGW WenKai GB", "霞鹜文楷 GB", "Kaiti SC", "STKaiti", "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", -apple-system, sans-serif;
  font-size: 28px;
  font-weight: 500;
  letter-spacing: 0.03em;
  line-height: 1.5;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  text-rendering: optimizeLegibility;
}

/* 한어병음 전용 타이포그래피 */
.pinyin {
  font-family: "Avenir Next", "Lucida Grande", "Helvetica Neue", -apple-system, sans-serif;
  font-size: 19px;
  font-weight: 500;
  color: #4b5563;
  margin-top: 10px;
  letter-spacing: 0.035em;
  font-feature-settings: "liga" 1;
}

.deck {
  text-align: right;
  font-size: 11px;
  color: #9ca3af;
  font-weight: 400;
  margin-top: 16px;
}

/* --- 플립 애니메이션 --- */
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

/* --- 다크모드 대응 --- */
@media (prefers-color-scheme: dark) {
  .card { background: #191919; color: #e3e3e3; border-color: #2f2f2f; }
  .title, .zh-sentence { color: #f9fafb; }
  .pinyin { color: #9ca3af; }
  .deck { color: #6b7280; }
}

.card.nightMode { background: #1f2937; color: #f3f4f6; border-color: #374151; }
.card.nightMode hr { border-top-color: #374151; }
.card.nightMode .title, .card.nightMode .zh-sentence { color: #f9fafb; }
.card.nightMode .pinyin { color: #9ca3af; }
.card.nightMode .deck { color: #6b7280; }
"""

# POS & Tier Badge Helper Script for Chinese Vocabulary
POS_HELPER_JS = r"""<script>
(function() {
  var POS_LABEL_MAP = {
    'v': 'v', '동사': 'v', 'verb': 'v',
    'n': 'n', '명사': 'n', 'noun': 'n',
    'adj': 'adj', '형용사': 'adj',
    'adv': 'adv', '부사': 'adv',
    'pron': 'pron', '대명사': 'pron',
    'num': 'num', '수사': 'num',
    'mw': 'mw', '양사': 'mw', 'cl': 'mw',
    'prep': 'prep', '전치사': 'prep', '개사': 'prep',
    'conj': 'conj', '접속사': 'conj', '연사': 'conj',
    'aux': 'aux', '조동사': 'aux',
    'part': 'part', '조사': 'part',
    'int': 'int', '감탄사': 'int',
    'idiom': 'idiom', '어구': 'idiom', '문장': 'idiom'
  };

  var POS_CLASS_MAP = {
    'v': 'v', 'n': 'n', 'adj': 'adj', 'adv': 'adv',
    'pron': 'pron', 'num': 'num', 'mw': 'mw',
    'prep': 'prep', 'conj': 'conj', 'aux': 'aux',
    'part': 'part', 'int': 'idiom', 'idiom': 'idiom'
  };

  var HSK_MAP = {
    'hsk::1': ['HSK 1', 'tier-1'],
    'hsk::2': ['HSK 2', 'tier-2'],
    'hsk::3': ['HSK 3', 'tier-3'],
    'hsk::4': ['HSK 4', 'tier-4'],
    'hsk::5': ['HSK 5', 'tier-5'],
    'hsk::6': ['HSK 6', 'tier-6']
  };

  document.querySelectorAll(".pos-raw").forEach(function(el) {
    var raw = el.getAttribute("data-pos") || "";
    var tagsRaw = el.getAttribute("data-tags") || "";
    var parts = raw.split(",").map(function(s) { return s.trim(); }).filter(Boolean);

    var g = document.createElement("span");
    g.style.cssText = "display:inline-flex;gap:4px;margin-left:6px;vertical-align:middle;";

    // 1. 품사 뱃지 (영문 약어)
    parts.forEach(function(p) {
      var low = p.toLowerCase();
      var label = POS_LABEL_MAP[low] || p;
      var cls = POS_CLASS_MAP[label] || 'idiom';
      var b = document.createElement("span");
      b.className = "pos " + cls;
      b.textContent = label;
      g.appendChild(b);
    });

    // 2. HSK 난이도 뱃지
    var tags = tagsRaw.split(/\s+/).filter(Boolean);
    for (var i = 0; i < tags.length; i++) {
      var info = HSK_MAP[tags[i]];
      if (info) {
        var tb = document.createElement("span");
        tb.className = "tier-badge " + info[1];
        tb.textContent = info[0];
        g.appendChild(tb);
        break;
      }
    }

    el.parentNode.replaceChild(g, el);
  });
})();
</script>"""

FLIP_ANIMATION_JS = r"""<script>
(function() {
  function trigger() {
    var c = document.querySelector(".card");
    if (c) { c.classList.remove("anim-ready"); void c.offsetWidth; c.classList.add("anim-ready"); }
  }
  if (typeof onUpdateHook !== "undefined") { onUpdateHook.push(trigger); } else { trigger(); }
})();
</script>"""

# ==============================================================================
# 3. CHINESE VOCABULARY TEMPLATES
# ==============================================================================

# Card 1 Front: Korean Meaning -> Cloze test Chinese word in sentence
ZH_VOCAB_CARD1_FRONT = POS_HELPER_JS + r"""
<div class="title">
  {{뜻}} <span class="pos-raw" data-pos="{{품사}}" data-tags="{{Tags}}"></span>
</div>

<div class="photo">{{사진}}</div>

<!-- 예문 빈칸 박스 -->
<div class="example zh-text" id="cloze-example" lang="zh-Hans">
  <span id="cloze-raw-word" style="display:none;">{{단어}}</span>
  <span id="cloze-raw-pinyin" style="display:none;">{{한어병음}}</span>
  <span id="cloze-raw-sentence" style="display:none;">{{예문}}</span>
  <div id="cloze-display"></div>
</div>

<script>
(function() {
  function renderCloze() {
    var box = document.getElementById("cloze-example");
    var wordEl = document.getElementById("cloze-raw-word");
    var pinyinEl = document.getElementById("cloze-raw-pinyin");
    var sentEl = document.getElementById("cloze-raw-sentence");
    var dispEl = document.getElementById("cloze-display");
    if (!box || !wordEl || !sentEl || !dispEl) return;
    if (box.hasAttribute("data-cloze-rendered")) return;

    var word = (wordEl.textContent || "").trim();
    var pinyin = (pinyinEl ? pinyinEl.textContent : "").trim();
    var rawSent = (sentEl.textContent || "").trim();

    if (!word || !rawSent) {
      box.style.display = "none";
      return;
    }

    var sentences = rawSent.split("|||").map(function(s) { return s.trim(); }).filter(Boolean);
    if (!sentences.length) {
      box.style.display = "none";
      return;
    }

    var normPinyin = pinyin.normalize ? pinyin.normalize("NFD").replace(/[\u0300-\u036f]/g, "") : pinyin;
    var cleanPinyin = normPinyin.replace(/^[^a-zA-Z]+/, "");
    var firstLetter = cleanPinyin ? cleanPinyin.charAt(0).toLowerCase() : "";

    // 1. 단어가 그대로 온전히 포함된 예문 우선 탐색 (Exact Match)
    var exactCandidates = [];
    for (var i = 0; i < sentences.length; i++) {
      var s = sentences[i];
      var m = s.match(/^([^(]+)(?:\s*\((.*)\))?$/);
      var hz = m ? m[1].trim() : s;
      if (hz.indexOf(word) !== -1) {
        exactCandidates.push({ full: s, hanzi: hz, sub: m && m[2] ? m[2].trim() : "", mode: "exact" });
      }
    }

    var selected = null;
    if (exactCandidates.length > 0) {
      selected = exactCandidates[Math.floor(Math.random() * exactCandidates.length)];
      var idx = selected.hanzi.indexOf(word);
      var blankLen = Math.max(1, word.length * 2 - 1);
      var blankStr = (firstLetter || "_") + "_".repeat(blankLen);
      var blankTag = '<span class="cloze-blank">' + blankStr + '</span>';
      selected.html = selected.hanzi.slice(0, idx) + blankTag + selected.hanzi.slice(idx + word.length);
    } else if (word.indexOf("...") !== -1) {
      // 2. 상관접속사 분리 매칭 (A...B)
      var pair = word.split("...").map(function(p) { return p.trim(); }).filter(Boolean);
      if (pair.length === 2) {
        var p1 = pair[0], p2 = pair[1];
        var pairRegex = new RegExp(p1 + "([^" + p1 + p2 + "]{1,8}?)" + p2);
        for (var k = 0; k < sentences.length; k++) {
          var sk = sentences[k];
          var mk = sk.match(/^([^(]+)(?:\s*\((.*)\))?$/);
          var hzk = mk ? mk[1].trim() : sk;
          var mp = hzk.match(pairRegex);
          if (mp) {
            var b1 = '<span class="cloze-blank">' + (firstLetter || "_") + "___</span>";
            var b2 = '<span class="cloze-blank">____</span>';
            selected = {
              full: sk,
              hanzi: hzk,
              sub: mk && mk[2] ? mk[2].trim() : "",
              mode: "pair",
              p1: p1,
              p2: p2,
              html: hzk.slice(0, mp.index) + b1 + mp[1] + b2 + hzk.slice(mp.index + mp[0].length)
            };
            break;
          }
        }
      }
    } else if (word.length === 2) {
      // 3. 이합동사 분리 매칭 (2음절 AB -> A...B)
      var c1 = word.charAt(0);
      var c2 = word.charAt(1);
      var sepRegex = new RegExp(c1 + "([^" + c1 + c2 + "]{1,5}?)" + c2);
      var splitCandidates = [];

      for (var j = 0; j < sentences.length; j++) {
        var s2 = sentences[j];
        var m2 = s2.match(/^([^(]+)(?:\s*\((.*)\))?$/);
        var hz2 = m2 ? m2[1].trim() : s2;
        var matchSep = hz2.match(sepRegex);
        if (matchSep) {
          splitCandidates.push({
            full: s2,
            hanzi: hz2,
            sub: m2 && m2[2] ? m2[2].trim() : "",
            mode: "split",
            matchIndex: matchSep.index,
            matchFull: matchSep[0],
            middle: matchSep[1]
          });
        }
      }

      if (splitCandidates.length > 0) {
        selected = splitCandidates[Math.floor(Math.random() * splitCandidates.length)];
        var b1 = '<span class="cloze-blank">' + (firstLetter || "_") + "_</span>";
        var b2 = '<span class="cloze-blank">__</span>';
        var replacement = b1 + selected.middle + b2;
        selected.html = selected.hanzi.slice(0, selected.matchIndex) + replacement + selected.hanzi.slice(selected.matchIndex + selected.matchFull.length);
      }
    }

    // 4. 매칭 실패 시: 정답 날것 노출 방지를 위해 예문 박스 숨김
    if (!selected) {
      box.style.display = "none";
      return;
    }

    dispEl.innerHTML = selected.html;

    try {
      sessionStorage.setItem("anki_zh_cloze_word", word);
      sessionStorage.setItem("anki_zh_cloze_sentence", selected.full);
      sessionStorage.setItem("anki_zh_cloze_mode", selected.mode || "exact");
    } catch(e) {}

    box.setAttribute("data-cloze-rendered", "true");
  }

  renderCloze();
  if (typeof onUpdateHook !== "undefined") {
    onUpdateHook.push(renderCloze);
  }
})();
</script>

<div class="deck">{{Deck}}</div>
"""

# Card 1 Back: Meaning on top, <hr>, Word + Audio + Pinyin below
ZH_VOCAB_CARD1_BACK = FLIP_ANIMATION_JS + POS_HELPER_JS + r"""
<div class="title">
  {{뜻}} <span class="pos-raw" data-pos="{{품사}}" data-tags="{{Tags}}"></span>
</div>

<div class="photo">{{사진}}</div>

<hr>

<div class="word zh-text" lang="zh-Hans">
  {{단어}} {{소리}}
</div>
<div class="pinyin" lang="zh-Latn">{{한어병음}}</div>

<div class="example zh-text" id="back-example-box" lang="zh-Hans">
  <span id="back-raw-word" style="display:none;">{{단어}}</span>
  <span id="back-raw-sentence" style="display:none;">{{예문}}</span>
  <div id="back-primary-sentence"></div>
</div>

<script>
(function() {
  function renderBack() {
    var box = document.getElementById("back-example-box");
    var wordEl = document.getElementById("back-raw-word");
    var sentEl = document.getElementById("back-raw-sentence");
    var outEl = document.getElementById("back-primary-sentence");
    if (!box || !wordEl || !sentEl || !outEl) return;

    var word = (wordEl.textContent || "").trim();
    var rawSent = (sentEl.textContent || "").trim();

    if (!rawSent) {
      box.style.display = "none";
      return;
    }

    var sentences = rawSent.split("|||").map(function(s) { return s.trim(); }).filter(Boolean);
    if (!sentences.length) {
      box.style.display = "none";
      return;
    }

    var chosen = sentences[0];
    try {
      var savedWord = sessionStorage.getItem("anki_zh_cloze_word");
      var savedSent = sessionStorage.getItem("anki_zh_cloze_sentence");
      if (savedWord === word && savedSent && sentences.indexOf(savedSent) !== -1) {
        chosen = savedSent;
      }
    } catch(e) {}

    var match = chosen.match(/^([^(]+)(?:\s*\((.*)\))?$/);
    var hanziPart = match ? match[1].trim() : chosen;
    var subPart = match && match[2] ? match[2].trim() : "";

    var idx = hanziPart.indexOf(word);
    var html = hanziPart;
    if (idx !== -1) {
      var hlTag = '<span class="example-highlight">' + word + '</span>';
      html = hanziPart.slice(0, idx) + hlTag + hanziPart.slice(idx + word.length);
    } else if (word.indexOf("...") !== -1) {
      var pair = word.split("...").map(function(p) { return p.trim(); }).filter(Boolean);
      if (pair.length === 2) {
        var pairRegex = new RegExp(pair[0] + "(.*?)" + pair[1]);
        var mp = hanziPart.match(pairRegex);
        if (mp) {
          var h1 = '<span class="example-highlight">' + pair[0] + '</span>';
          var h2 = '<span class="example-highlight">' + pair[1] + '</span>';
          html = hanziPart.slice(0, mp.index) + h1 + mp[1] + h2 + hanziPart.slice(mp.index + mp[0].length);
        }
      }
    } else if (word.length === 2) {
      var c1 = word.charAt(0);
      var c2 = word.charAt(1);
      var sepRegex = new RegExp(c1 + "([^" + c1 + c2 + "]{1,5}?)" + c2);
      var mSep = hanziPart.match(sepRegex);
      if (mSep) {
        var hl1 = '<span class="example-highlight">' + c1 + '</span>';
        var hl2 = '<span class="example-highlight">' + c2 + '</span>';
        html = hanziPart.slice(0, mSep.index) + hl1 + mSep[1] + hl2 + hanziPart.slice(mSep.index + mSep[0].length);
      }
    }

    if (subPart) {
      html += '<span class="pinyin-sub">(' + subPart + ')</span>';
    }

    outEl.innerHTML = html;
  }

  renderBack();
  if (typeof onUpdateHook !== "undefined") {
    onUpdateHook.push(renderBack);
  }
})();
</script>

<div class="deck">{{Deck}}</div>
"""

# Card 2 Front: Chinese Word -> Test recognition
ZH_VOCAB_CARD2_FRONT = POS_HELPER_JS + r"""
<div class="title zh-text" lang="zh-Hans">
  {{단어}} <span class="pos-raw" data-pos="{{품사}}" data-tags="{{Tags}}"></span>
</div>

<div class="deck">{{Deck}}</div>
"""

# Card 2 Back: Chinese Word + Audio on top, Pinyin, Photo, <hr>, Meaning below
ZH_VOCAB_CARD2_BACK = FLIP_ANIMATION_JS + POS_HELPER_JS + r"""
<div class="title zh-text" lang="zh-Hans">
  {{단어}} {{소리}}
  <span class="pos-raw" data-pos="{{품사}}" data-tags="{{Tags}}"></span>
</div>
<div class="pinyin" lang="zh-Latn">{{한어병음}}</div>
<div class="photo">{{사진}}</div>

<hr>

<div class="word">
  {{뜻}}
</div>

<div class="example zh-text" id="back-example-box-2" lang="zh-Hans">
  <span id="back-raw-word-2" style="display:none;">{{단어}}</span>
  <span id="back-raw-sentence-2" style="display:none;">{{예문}}</span>
  <div id="back-primary-sentence-2"></div>
</div>

<script>
(function() {
  function renderBack2() {
    var box = document.getElementById("back-example-box-2");
    var wordEl = document.getElementById("back-raw-word-2");
    var sentEl = document.getElementById("back-raw-sentence-2");
    var outEl = document.getElementById("back-primary-sentence-2");
    if (!box || !wordEl || !sentEl || !outEl) return;

    var word = (wordEl.textContent || "").trim();
    var rawSent = (sentEl.textContent || "").trim();
    if (!rawSent) {
      box.style.display = "none";
      return;
    }
    var sentences = rawSent.split("|||").map(function(s) { return s.trim(); }).filter(Boolean);
    if (!sentences.length) {
      box.style.display = "none";
      return;
    }
    var chosen = sentences[0];
    var match = chosen.match(/^([^(]+)(?:\s*\((.*)\))?$/);
    var hanziPart = match ? match[1].trim() : chosen;
    var subPart = match && match[2] ? match[2].trim() : "";

    var idx = hanziPart.indexOf(word);
    var html = hanziPart;
    if (idx !== -1) {
      var hlTag = '<span class="example-highlight">' + word + '</span>';
      html = hanziPart.slice(0, idx) + hlTag + hanziPart.slice(idx + word.length);
    } else if (word.indexOf("...") !== -1) {
      var pair = word.split("...").map(function(p) { return p.trim(); }).filter(Boolean);
      if (pair.length === 2) {
        var pairRegex = new RegExp(pair[0] + "(.*?)" + pair[1]);
        var mp = hanziPart.match(pairRegex);
        if (mp) {
          var h1 = '<span class="example-highlight">' + pair[0] + '</span>';
          var h2 = '<span class="example-highlight">' + pair[1] + '</span>';
          html = hanziPart.slice(0, mp.index) + h1 + mp[1] + h2 + hanziPart.slice(mp.index + mp[0].length);
        }
      }
    } else if (word.length === 2) {
      var c1 = word.charAt(0);
      var c2 = word.charAt(1);
      var sepRegex = new RegExp(c1 + "([^" + c1 + c2 + "]{1,5}?)" + c2);
      var mSep = hanziPart.match(sepRegex);
      if (mSep) {
        var hl1 = '<span class="example-highlight">' + c1 + '</span>';
        var hl2 = '<span class="example-highlight">' + c2 + '</span>';
        html = hanziPart.slice(0, mSep.index) + hl1 + mSep[1] + hl2 + hanziPart.slice(mSep.index + mSep[0].length);
      }
    }
    if (subPart) {
      html += '<span class="pinyin-sub">(' + subPart + ')</span>';
    }
    outEl.innerHTML = html;
  }
  renderBack2();
  if (typeof onUpdateHook !== "undefined") {
    onUpdateHook.push(renderBack2);
  }
})();
</script>

<div class="deck">{{Deck}}</div>
"""

# ==============================================================================
# 4. CHINESE SENTENCE TEMPLATES (Super clean: NO badges!)
# ==============================================================================

# Card 1 Front: Korean sentence
ZH_SENT_CARD1_FRONT = r"""
<div class="title">
  {{뜻}}
</div>
<div class="deck">{{Deck}}</div>
"""

# Card 1 Back: Korean sentence on top, <hr>, Chinese sentence + audio + pinyin
ZH_SENT_CARD1_BACK = FLIP_ANIMATION_JS + r"""
<div class="title">
  {{뜻}}
</div>

<hr>

<div class="title zh-sentence" lang="zh-Hans">
  {{문장}} {{소리}}
  <div class="pinyin" lang="zh-Latn">{{한어병음}}</div>
</div>

<div class="deck">{{Deck}}</div>
"""

# Card 2 Front: Chinese sentence (Text only, audio moved to back for active recall)
ZH_SENT_CARD2_FRONT = r"""
<div class="title zh-sentence" lang="zh-Hans">
  {{문장}}
</div>
<div class="deck">{{Deck}}</div>
"""

# Card 2 Back: Chinese sentence on top + pinyin, <hr>, Korean sentence below
ZH_SENT_CARD2_BACK = FLIP_ANIMATION_JS + r"""
<div class="title zh-sentence" lang="zh-Hans">
  {{문장}} {{소리}}
  <div class="pinyin" lang="zh-Latn">{{한어병음}}</div>
</div>

<hr>

<div class="title">
  {{뜻}}
</div>

<div class="deck">{{Deck}}</div>
"""


def deploy():
    # Release editor lock by selecting an English card
    try:
        os.system("osascript -e 'tell application \"Anki\" to activate' -e 'tell application \"System Events\" to key code 53'")
        en_cards = AnkiConnector.invoke("findCards", query='"deck:1. Language::1.1. English::Vocabulary"')
        if en_cards:
            AnkiConnector.invoke("guiSelectCard", card=en_cards[0])
    except Exception:
        pass

    print("[*] Deploying unified design templates to Chinese Vocabulary...")
    vocab_tpls = AnkiConnector.invoke("modelTemplates", modelName=MODEL_ZH_VOCAB)
    vocab_tpls["카드 1"]["Front"] = ZH_VOCAB_CARD1_FRONT
    vocab_tpls["카드 1"]["Back"] = ZH_VOCAB_CARD1_BACK
    vocab_tpls["카드 2"]["Front"] = ZH_VOCAB_CARD2_FRONT
    vocab_tpls["카드 2"]["Back"] = ZH_VOCAB_CARD2_BACK
    AnkiConnector.update_model_templates(MODEL_ZH_VOCAB, vocab_tpls)
    AnkiConnector.invoke("updateModelStyling", model={"name": MODEL_ZH_VOCAB, "css": CHINESE_VOCAB_CSS})
    print("  ✓ Chinese Vocabulary templates & styling updated.")

    print("[*] Deploying unified design templates to Chinese Sentence (NO badges)...")
    sent_tpls = AnkiConnector.invoke("modelTemplates", modelName=MODEL_ZH_SENTENCE)
    sent_tpls["카드 1"]["Front"] = ZH_SENT_CARD1_FRONT
    sent_tpls["카드 1"]["Back"] = ZH_SENT_CARD1_BACK
    sent_tpls["카드 2"]["Front"] = ZH_SENT_CARD2_FRONT
    sent_tpls["카드 2"]["Back"] = ZH_SENT_CARD2_BACK
    AnkiConnector.update_model_templates(MODEL_ZH_SENTENCE, sent_tpls)
    AnkiConnector.invoke("updateModelStyling", model={"name": MODEL_ZH_SENTENCE, "css": CHINESE_SENTENCE_CSS})
    print("  ✓ Chinese Sentence templates & styling updated (Badges completely removed).")

    cfg_file = BASE_DIR / "data" / "design_config.json"
    if cfg_file.exists():
        with open(cfg_file, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        cfg[MODEL_ZH_VOCAB] = {"css": CHINESE_VOCAB_CSS, "templates": vocab_tpls}
        cfg[MODEL_ZH_SENTENCE] = {"css": CHINESE_SENTENCE_CSS, "templates": sent_tpls}
        with open(cfg_file, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        print("  ✓ data/design_config.json updated.")

    print("\n✅ All Chinese card designs, templates, and cloze matching successfully deployed!")


if __name__ == "__main__":
    deploy()
