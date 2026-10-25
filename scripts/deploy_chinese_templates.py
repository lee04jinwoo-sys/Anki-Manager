"""
Deploy Modern Apple-style templates for Chinese Vocabulary and Chinese Sentence models in Anki.
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

# Common base CSS matching English design system
CHINESE_CSS = r"""
.card {
  font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif;
  font-size: 16px;
  text-align: center;
  color: #1d1d1f;
  background-color: #fbfbfd;
  line-height: 1.6;
  padding: 30px 20px;
  max-width: 600px;
  margin: 0 auto;
  box-sizing: border-box;
}

.card.nightMode {
  background-color: #000000;
  color: #f5f5f7;
}

.title {
  font-size: 1.5rem;
  font-weight: 700;
  color: #1d1d1f;
  margin-bottom: 16px;
  word-break: keep-all;
}

.card.nightMode .title {
  color: #f5f5f7;
}

.pos {
  font-size: 0.8rem;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 6px;
  background-color: #f0f0f2;
  color: #86868b;
  margin-left: 6px;
  vertical-align: middle;
  display: inline-block;
}

.card.nightMode .pos {
  background-color: #1c1c1e;
  color: #98989d;
}

.photo img {
  max-width: 100%;
  max-height: 240px;
  border-radius: 12px;
  margin: 12px 0;
  object-fit: cover;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
}

hr {
  border: none;
  border-top: 1px solid #d2d2d7;
  margin: 24px 0;
}

.card.nightMode hr {
  border-top-color: #38383a;
}

.word {
  font-size: 1.6rem;
  font-weight: 700;
  color: #1d1d1f;
  margin: 12px 0;
}

.card.nightMode .word {
  color: #f5f5f7;
}

.word-zh {
  margin: 16px 0;
}

.word-zh .term {
  font-size: 2.4rem;
  font-weight: 700;
  color: #1d1d1f;
  letter-spacing: 1px;
}

.card.nightMode .word-zh .term {
  color: #f5f5f7;
}

.pinyin {
  font-size: 1.15rem;
  font-weight: 500;
  color: #0071e3;
  margin-top: 6px;
  letter-spacing: 0.5px;
}

.card.nightMode .pinyin {
  color: #38bdf8;
}

.example {
  background-color: #ffffff;
  border: 1px solid #e5e5ea;
  border-radius: 14px;
  padding: 16px 20px;
  margin: 20px 0;
  font-size: 1.15rem;
  line-height: 1.6;
  text-align: left;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
}

.card.nightMode .example {
  background-color: #1c1c1e;
  border-color: #2c2c2e;
  box-shadow: none;
}

.example-main {
  font-weight: 500;
  color: #1d1d1f;
}

.card.nightMode .example-main {
  color: #f5f5f7;
}

.example-sub {
  font-size: 0.95rem;
  color: #86868b;
  margin-top: 8px;
  line-height: 1.4;
}

.card.nightMode .example-sub {
  color: #98989d;
}

.cloze-blank {
  color: #0071e3;
  font-weight: 700;
  letter-spacing: 2px;
  text-decoration: underline;
  text-decoration-color: #0071e3;
  text-underline-offset: 4px;
}

.card.nightMode .cloze-blank {
  color: #38bdf8;
  text-decoration-color: #38bdf8;
}

.example-highlight {
  color: #0071e3;
  font-weight: 700;
  text-decoration: underline;
  text-decoration-color: #0071e3;
  text-underline-offset: 4px;
}

.card.nightMode .example-highlight {
  color: #38bdf8;
  text-decoration-color: #38bdf8;
}

.deck {
  font-size: 0.75rem;
  color: #86868b;
  margin-top: 24px;
  text-align: right;
}

.card.nightMode .deck {
  color: #636366;
}

@keyframes cardFlip {
  0%   { opacity: 0; transform: perspective(700px) rotateY(-90deg) scale(0.95); }
  60%  { opacity: 1; transform: perspective(700px) rotateY(6deg) scale(1.01); }
  80%  { transform: perspective(700px) rotateY(-2deg) scale(1.0); }
  100% { opacity: 1; transform: perspective(700px) rotateY(0deg) scale(1); }
}

@keyframes fadeUp {
  from { opacity: 0; transform: translateY(8px); }
  to   { opacity: 1; transform: translateY(0); }
}

.card.anim-ready {
  animation: cardFlip 0.45s cubic-bezier(0.4, 0, 0.2, 1) both;
}

.card.anim-ready hr ~ * {
  animation: fadeUp 0.3s ease 0.25s both;
}
"""

ZH_VOCAB_CARD1_FRONT = r"""<div class="title">
  {{뜻}} <span class="pos-raw" data-pos="{{품사}}"></span>
</div>

<div class="photo">{{사진}}</div>

<div class="example" id="cloze-example">
  <span id="cloze-raw-word" style="display:none;">{{단어}}</span>
  <span id="cloze-raw-pinyin" style="display:none;">{{한어병음}}</span>
  <span id="cloze-raw-sentence" style="display:none;">{{예문}}</span>
  <div id="cloze-display"></div>
</div>

<script>
(function() {
  document.querySelectorAll(".pos-raw").forEach(function(el) {
    var raw = el.getAttribute("data-pos") || "";
    var parts = raw.split(",").map(function(s) { return s.trim(); }).filter(Boolean);
    if (!parts.length) return;
    var g = document.createElement("span");
    parts.forEach(function(p) {
      var b = document.createElement("span");
      b.className = "pos";
      b.textContent = p;
      g.appendChild(b);
    });
    el.parentNode.replaceChild(g, el);
  });
})();
</script>

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

    var chosenIdx = Math.floor(Math.random() * sentences.length);
    var chosen = sentences[chosenIdx];

    // Separate main Hanzi sentence from (pinyin / meaning) notes
    var match = chosen.match(/^([^(]+)(?:\s*\((.*)\))?$/);
    var hanziPart = match ? match[1].trim() : chosen;

    var normPinyin = pinyin.normalize ? pinyin.normalize("NFD").replace(/[\u0300-\u036f]/g, "") : pinyin;
    var cleanPinyin = normPinyin.replace(/^[^a-zA-Z]+/, "");
    var firstLetter = cleanPinyin ? cleanPinyin.charAt(0).toLowerCase() : "";

    var idx = hanziPart.indexOf(word);
    var html = hanziPart;
    if (idx !== -1) {
      var blankLen = Math.max(1, word.length * 2 - 1);
      var blankStr = (firstLetter || "_") + "_".repeat(blankLen);
      var blankTag = '<span class="cloze-blank">' + blankStr + '</span>';
      html = hanziPart.slice(0, idx) + blankTag + hanziPart.slice(idx + word.length);
    }

    dispEl.innerHTML = html;

    try {
      sessionStorage.setItem("anki_zh_cloze_word", word);
      sessionStorage.setItem("anki_zh_cloze_sentence", chosen);
    } catch(e) {}

    box.setAttribute("data-cloze-rendered", "true");
  }

  renderCloze();
  if (typeof onUpdateHook !== "undefined") {
    onUpdateHook.push(renderCloze);
  }
})();
</script>

<div class="deck">{{Deck}}</div>"""

ZH_VOCAB_CARD1_BACK = r"""<script>
(function() {
  function trigger() {
    var c = document.querySelector(".card");
    if (c) { c.classList.remove("anim-ready"); void c.offsetWidth; c.classList.add("anim-ready"); }
  }
  if (typeof onUpdateHook !== "undefined") { onUpdateHook.push(trigger); } else { trigger(); }
})();
</script>

<div class="title">
  {{뜻}} <span class="pos-raw" data-pos="{{품사}}"></span>
</div>

<div class="photo">{{사진}}</div>

<hr>

<div class="word-zh">
  <span class="term">{{단어}}</span> {{소리}}
  <div class="pinyin">{{한어병음}}</div>
</div>

<div class="example" id="back-example-box">
  <span id="back-raw-word" style="display:none;">{{단어}}</span>
  <span id="back-raw-sentence" style="display:none;">{{예문}}</span>
  <div id="back-primary-sentence"></div>
</div>

<script>
(function() {
  document.querySelectorAll(".pos-raw").forEach(function(el) {
    var raw = el.getAttribute("data-pos") || "";
    var parts = raw.split(",").map(function(s) { return s.trim(); }).filter(Boolean);
    if (!parts.length) return;
    var g = document.createElement("span");
    parts.forEach(function(p) {
      var b = document.createElement("span");
      b.className = "pos";
      b.textContent = p;
      g.appendChild(b);
    });
    el.parentNode.replaceChild(g, el);
  });
})();
</script>

<script>
(function() {
  function renderBackExample() {
    var box = document.getElementById("back-example-box");
    var wordEl = document.getElementById("back-raw-word");
    var sentEl = document.getElementById("back-raw-sentence");
    var primaryEl = document.getElementById("back-primary-sentence");
    if (!box || !wordEl || !sentEl || !primaryEl) return;

    var word = (wordEl.textContent || "").trim();
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
    var highlit = hanziPart;
    if (idx !== -1) {
      highlit = hanziPart.slice(0, idx) + '<span class="example-highlight">' + word + '</span>' + hanziPart.slice(idx + word.length);
    }

    var out = '<div class="example-main">' + highlit + '</div>';
    if (subPart) {
      out += '<div class="example-sub">(' + subPart + ')</div>';
    }
    primaryEl.innerHTML = out;
  }

  renderBackExample();
  if (typeof onUpdateHook !== "undefined") {
    onUpdateHook.push(renderBackExample);
  }
})();
</script>

<div class="deck">{{Deck}}</div>"""

ZH_VOCAB_CARD2_FRONT = r"""<div class="title">
  <span class="term" style="font-size:2.6rem; font-weight:700;">{{단어}}</span>
  <span class="pos-raw" data-pos="{{품사}}"></span>
</div>

<div class="photo">{{사진}}</div>

<script>
(function() {
  document.querySelectorAll(".pos-raw").forEach(function(el) {
    var raw = el.getAttribute("data-pos") || "";
    var parts = raw.split(",").map(function(s) { return s.trim(); }).filter(Boolean);
    if (!parts.length) return;
    var g = document.createElement("span");
    parts.forEach(function(p) {
      var b = document.createElement("span");
      b.className = "pos";
      b.textContent = p;
      g.appendChild(b);
    });
    el.parentNode.replaceChild(g, el);
  });
})();
</script>

<div class="deck">{{Deck}}</div>"""

ZH_VOCAB_CARD2_BACK = r"""<script>
(function() {
  function trigger() {
    var c = document.querySelector(".card");
    if (c) { c.classList.remove("anim-ready"); void c.offsetWidth; c.classList.add("anim-ready"); }
  }
  if (typeof onUpdateHook !== "undefined") { onUpdateHook.push(trigger); } else { trigger(); }
})();
</script>

<div class="word-zh">
  <span class="term">{{단어}}</span> {{소리}}
  <div class="pinyin">{{한어병음}}</div>
  <span class="pos-raw" data-pos="{{품사}}"></span>
</div>

<div class="photo">{{사진}}</div>

<hr>

<div class="word">{{뜻}}</div>

<div class="example" id="back-example-box">
  <span id="back-raw-word" style="display:none;">{{단어}}</span>
  <span id="back-raw-sentence" style="display:none;">{{예문}}</span>
  <div id="back-primary-sentence"></div>
</div>

<script>
(function() {
  document.querySelectorAll(".pos-raw").forEach(function(el) {
    var raw = el.getAttribute("data-pos") || "";
    var parts = raw.split(",").map(function(s) { return s.trim(); }).filter(Boolean);
    if (!parts.length) return;
    var g = document.createElement("span");
    parts.forEach(function(p) {
      var b = document.createElement("span");
      b.className = "pos";
      b.textContent = p;
      g.appendChild(b);
    });
    el.parentNode.replaceChild(g, el);
  });
})();
</script>

<script>
(function() {
  function renderBackExample() {
    var box = document.getElementById("back-example-box");
    var wordEl = document.getElementById("back-raw-word");
    var sentEl = document.getElementById("back-raw-sentence");
    var primaryEl = document.getElementById("back-primary-sentence");
    if (!box || !wordEl || !sentEl || !primaryEl) return;

    var word = (wordEl.textContent || "").trim();
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

    var chosen = sentences[0];
    var match = chosen.match(/^([^(]+)(?:\s*\((.*)\))?$/);
    var hanziPart = match ? match[1].trim() : chosen;
    var subPart = match && match[2] ? match[2].trim() : "";

    var idx = hanziPart.indexOf(word);
    var highlit = hanziPart;
    if (idx !== -1) {
      highlit = hanziPart.slice(0, idx) + '<span class="example-highlight">' + word + '</span>' + hanziPart.slice(idx + word.length);
    }

    var out = '<div class="example-main">' + highlit + '</div>';
    if (subPart) {
      out += '<div class="example-sub">(' + subPart + ')</div>';
    }
    primaryEl.innerHTML = out;
  }

  renderBackExample();
  if (typeof onUpdateHook !== "undefined") {
    onUpdateHook.push(renderBackExample);
  }
})();
</script>

<div class="deck">{{Deck}}</div>"""

ZH_SENT_CARD1_FRONT = r"""<div class="example" style="font-size:1.4rem; text-align:center; padding:24px 20px;">
  {{문장}}
</div>

<div class="deck">{{Deck}}</div>"""

ZH_SENT_CARD1_BACK = r"""<script>
(function() {
  function trigger() {
    var c = document.querySelector(".card");
    if (c) { c.classList.remove("anim-ready"); void c.offsetWidth; c.classList.add("anim-ready"); }
  }
  if (typeof onUpdateHook !== "undefined") { onUpdateHook.push(trigger); } else { trigger(); }
})();
</script>

<div class="example" style="font-size:1.4rem; text-align:center; padding:24px 20px;">
  {{문장}} {{소리}}
  <div class="pinyin" style="margin-top:10px;">{{한어병음}}</div>
</div>

<hr>

<div class="title" style="font-size:1.3rem;">
  {{뜻}}
</div>

<div class="deck">{{Deck}}</div>"""

ZH_SENT_CARD2_FRONT = r"""<div class="title" style="font-size:1.3rem;">
  {{뜻}}
</div>

<div class="deck">{{Deck}}</div>"""

ZH_SENT_CARD2_BACK = r"""<script>
(function() {
  function trigger() {
    var c = document.querySelector(".card");
    if (c) { c.classList.remove("anim-ready"); void c.offsetWidth; c.classList.add("anim-ready"); }
  }
  if (typeof onUpdateHook !== "undefined") { onUpdateHook.push(trigger); } else { trigger(); }
})();
</script>

<div class="title" style="font-size:1.3rem;">
  {{뜻}}
</div>

<hr>

<div class="example" style="font-size:1.4rem; text-align:center; padding:24px 20px;">
  {{문장}} {{소리}}
  <div class="pinyin" style="margin-top:10px;">{{한어병음}}</div>
</div>

<div class="deck">{{Deck}}</div>"""


def deploy():
    print("[*] Updating Chinese Vocabulary templates...")
    vocab_tpls = AnkiConnector.invoke("modelTemplates", modelName=MODEL_ZH_VOCAB)
    vocab_tpls["카드 1"]["Front"] = ZH_VOCAB_CARD1_FRONT
    vocab_tpls["카드 1"]["Back"] = ZH_VOCAB_CARD1_BACK
    vocab_tpls["카드 2"]["Front"] = ZH_VOCAB_CARD2_FRONT
    vocab_tpls["카드 2"]["Back"] = ZH_VOCAB_CARD2_BACK
    AnkiConnector.update_model_templates(MODEL_ZH_VOCAB, vocab_tpls)
    AnkiConnector.invoke("updateModelStyling", model={"name": MODEL_ZH_VOCAB, "css": CHINESE_CSS})
    print("  ✓ Chinese Vocabulary templates & styling updated.")

    print("[*] Updating Chinese Sentence templates...")
    sent_tpls = AnkiConnector.invoke("modelTemplates", modelName=MODEL_ZH_SENTENCE)
    sent_tpls["카드 1"]["Front"] = ZH_SENT_CARD1_FRONT
    sent_tpls["카드 1"]["Back"] = ZH_SENT_CARD1_BACK
    sent_tpls["카드 2"]["Front"] = ZH_SENT_CARD2_FRONT
    sent_tpls["카드 2"]["Back"] = ZH_SENT_CARD2_BACK
    AnkiConnector.update_model_templates(MODEL_ZH_SENTENCE, sent_tpls)
    AnkiConnector.invoke("updateModelStyling", model={"name": MODEL_ZH_SENTENCE, "css": CHINESE_CSS})
    print("  ✓ Chinese Sentence templates & styling updated.")

    cfg_file = BASE_DIR / "data" / "design_config.json"
    if cfg_file.exists():
        with open(cfg_file, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        cfg[MODEL_ZH_VOCAB] = {"css": CHINESE_CSS, "templates": vocab_tpls}
        cfg[MODEL_ZH_SENTENCE] = {"css": CHINESE_CSS, "templates": sent_tpls}
        with open(cfg_file, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        print("  ✓ data/design_config.json updated.")

if __name__ == "__main__":
    deploy()
