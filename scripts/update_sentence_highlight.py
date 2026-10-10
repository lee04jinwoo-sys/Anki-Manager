"""
Update English Sentence card template with:
- Dark Crimson color (#b91c1c / dark mode #f87171)
- Hover floating tooltip showing word, part-of-speech, and Korean meaning
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

os.environ["no_proxy"] = "*"
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

SENTENCE_BACK_TEMPLATE = r"""<style>
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

<div class="title" id="alm-sentence-title">
  <span id="alm-sentence-text">{{문장}}</span>{{소리}}
</div>

<!-- ANKI_LINK_MANAGER_SENTENCE_INLINE -->
<script>
(function() {
  function applyLinkedHighlight() {
    var textEl = document.getElementById("alm-sentence-text");
    if (!textEl) return;
    if (textEl.hasAttribute("data-linked-highlighted")) return;

    var rawText = (textEl.textContent || textEl.innerText || "").trim();
    if (!rawText) return;

    fetch("http://127.0.0.1:8001/api/links/badge/sentence?text=" + encodeURIComponent(rawText))
      .then(function(r) { return r.json(); })
      .then(function(d) {
        if (!d) return;
        var items = d.items;
        if (!items || items.length === 0) {
          if (d.words && d.words.length > 0) {
            items = d.words.map(function(w) { return { word: w, meaning: "", pos: "" }; });
          } else {
            return;
          }
        }

        var IRREGULARS = {
          "get": "(?:get|gets|getting|got|gotten)", "take": "(?:take|takes|taking|took|taken)",
          "make": "(?:make|makes|making|made)", "give": "(?:give|gives|giving|gave|given)",
          "come": "(?:come|comes|coming|came)", "go": "(?:go|goes|going|went|gone)",
          "see": "(?:see|sees|seeing|saw|seen)", "have": "(?:have|has|having|had)",
          "run": "(?:run|runs|running|ran)", "keep": "(?:keep|keeps|keeping|kept)",
          "find": "(?:find|finds|finding|found)", "fall": "(?:fall|falls|falling|fell|fallen)",
          "break": "(?:break|breaks|breaking|broke|broken)", "bring": "(?:bring|brings|bringing|brought)",
          "buy": "(?:buy|buys|buying|bought)", "catch": "(?:catch|catches|catching|caught)",
          "choose": "(?:choose|chooses|choosing|chose|chosen)", "do": "(?:do|does|doing|did|done)",
          "draw": "(?:draw|draws|drawing|drew|drawn)", "drive": "(?:drive|drives|driving|drove|driven)",
          "feel": "(?:feel|feels|feeling|felt)", "fly": "(?:fly|flies|flying|flew|flown)",
          "grow": "(?:grow|grows|growing|grew|grown)", "hear": "(?:hear|hears|hearing|heard)",
          "hold": "(?:hold|holds|holding|held)", "know": "(?:know|knows|knowing|knew|known)",
          "leave": "(?:leave|leaves|leaving|left)", "lose": "(?:lose|loses|losing|lost)",
          "pay": "(?:pay|pays|paying|paid)", "put": "(?:put|puts|putting)",
          "read": "(?:read|reads|reading)", "say": "(?:say|says|saying|said)",
          "send": "(?:send|sends|sending|sent)", "show": "(?:show|shows|showing|showed|shown)",
          "speak": "(?:speak|speaks|speaking|spoke|spoken)", "spend": "(?:spend|spends|spending|spent)",
          "stand": "(?:stand|stands|standing|stood)", "tell": "(?:tell|tells|telling|told)",
          "think": "(?:think|thinks|thinking|thought)", "wear": "(?:wear|wears|wearing|wore|worn)",
          "win": "(?:win|wins|winning|won)", "write": "(?:write|writes|writing|wrote|written)"
        };

        function escapeRegex(s) {
          var specials = ".*+?^${}()|[]/\\-";
          var out = "";
          for (var i = 0; i < s.length; i++) {
            var c = s.charAt(i);
            if (specials.indexOf(c) !== -1) {
              out += "\\" + c;
            } else {
              out += c;
            }
          }
          return out;
        }

        function buildTokenPattern(tok) {
          var tLower = tok.toLowerCase();
          if (IRREGULARS[tLower]) return IRREGULARS[tLower];
          var clean = escapeRegex(tLower);
          var stem = clean;
          if (stem.length > 3 && (stem.endsWith("e") || stem.endsWith("y"))) {
            stem = stem.slice(0, -1);
          }
          return stem + "[a-zA-Z]*";
        }

        var sorted = items.slice().sort(function(a, b) { return b.word.length - a.word.length; });
        var ranges = [];

        sorted.forEach(function(item) {
          var vocab = item.word;
          var rawTokens = vocab.split(/[\s/]+/);
          var tokens = rawTokens.filter(function(t) {
            return !/^(someone|somebody|sb|something|sth|one's|oneself|A|B|C|V|V-ing|to)$/i.test(t);
          });
          if (tokens.length === 0) tokens = rawTokens.filter(function(t) { return /^[a-zA-Z]+$/.test(t); });
          if (tokens.length === 0) tokens = rawTokens;

          var parts = tokens.map(buildTokenPattern);
          var sep = "(?:\\s+[\\w$\\'\\\"]+){0,4}\\s+";
          try {
            var regex = new RegExp("\\b(" + parts.join(sep) + ")\\b", "gi");
            var m;
            while ((m = regex.exec(rawText)) !== null) {
              var start = m.index;
              var end = start + m[0].length;
              var overlap = ranges.some(function(r) {
                return Math.max(start, r.start) < Math.min(end, r.end);
              });
              if (!overlap) {
                ranges.push({
                  start: start,
                  end: end,
                  word: item.word,
                  pos: item.pos || "",
                  meaning: item.meaning || ""
                });
              }
            }
          } catch(e) {}
        });

        if (ranges.length === 0) return;

        ranges.sort(function(a, b) { return a.start - b.start; });

        var out = "";
        var lastIdx = 0;
        ranges.forEach(function(r) {
          out += rawText.slice(lastIdx, r.start);
          var label = r.word;
          if (r.pos) label += " (" + r.pos + ")";
          if (r.meaning) label += ": " + r.meaning;
          var safeLabel = label.replace(/"/g, "&quot;");

          out += '<span class="linked-word" data-tooltip="' + safeLabel + '" title="' + safeLabel + '">' + rawText.slice(r.start, r.end) + '</span>';
          lastIdx = r.end;
        });
        out += rawText.slice(lastIdx);

        textEl.innerHTML = out;
        textEl.setAttribute("data-linked-highlighted", "true");
      })
      .catch(function() {});
  }

  applyLinkedHighlight();
  if (typeof onUpdateHook !== "undefined") {
    onUpdateHook.push(applyLinkedHighlight);
  }
})();
</script>
<style>
/* --- Linked Expression in Sentence (어두운 푸른 계열 인라인 강조 + 호버 툴팁) --- */
.linked-word {
  position: relative !important;
  display: inline !important;
  color: #1e40af !important; /* Deep Navy Blue (어두운 푸른 계열) */
  text-decoration: underline !important;
  text-decoration-color: rgba(30, 64, 175, 0.45) !important;
  text-decoration-thickness: 1.5px !important;
  text-underline-offset: 4px !important;
  font-weight: inherit !important;
  cursor: pointer !important;
  transition: all 0.15s ease !important;
}

.linked-word:hover {
  text-decoration-color: #1e40af !important;
  background-color: rgba(30, 64, 175, 0.08) !important;
  border-radius: 4px !important;
}

/* --- 플로팅 말풍선 툴팁 (단어 + 품사 + 한국어 뜻) --- */
.linked-word[data-tooltip]:hover::after {
  content: attr(data-tooltip);
  position: absolute;
  bottom: calc(100% + 7px);
  left: 50%;
  transform: translateX(-50%);
  background: #1f2937;
  color: #ffffff;
  padding: 5px 12px;
  font-size: 13px;
  font-weight: 500;
  line-height: 1.4;
  white-space: nowrap;
  max-width: 320px;
  border-radius: 7px;
  box-shadow: 0 4px 14px rgba(0, 0, 0, 0.18);
  pointer-events: none;
  z-index: 1000;
  opacity: 0;
  animation: almTooltipIn 0.15s cubic-bezier(0.4, 0, 0.2, 1) 0.05s forwards;
}

.linked-word[data-tooltip]:hover::before {
  content: "";
  position: absolute;
  bottom: calc(100% + 2px);
  left: 50%;
  transform: translateX(-50%);
  border-width: 5px 5px 0 5px;
  border-style: solid;
  border-color: #1f2937 transparent transparent transparent;
  pointer-events: none;
  z-index: 1000;
  opacity: 0;
  animation: almTooltipIn 0.15s cubic-bezier(0.4, 0, 0.2, 1) 0.05s forwards;
}

@keyframes almTooltipIn {
  from { opacity: 0; transform: translateX(-50%) translateY(3px); }
  to   { opacity: 1; transform: translateX(-50%) translateY(0); }
}

/* --- 다크 모드 (Night Mode) --- */
.card.nightMode .linked-word,
.nightMode .linked-word {
  color: #60a5fa !important; /* Soft Blue (다크모드 최적화 소프트 블루) */
  text-decoration-color: rgba(96, 165, 250, 0.5) !important;
}

.card.nightMode .linked-word:hover,
.nightMode .linked-word:hover {
  text-decoration-color: #60a5fa !important;
  background-color: rgba(96, 165, 250, 0.12) !important;
}

.card.nightMode .linked-word[data-tooltip]:hover::after,
.nightMode .linked-word[data-tooltip]:hover::after {
  background: #f3f4f6;
  color: #111827;
  box-shadow: 0 4px 14px rgba(0, 0, 0, 0.4);
}

.card.nightMode .linked-word[data-tooltip]:hover::before,
.nightMode .linked-word[data-tooltip]:hover::before {
  border-color: #f3f4f6 transparent transparent transparent;
}
</style>
<!-- /ANKI_LINK_MANAGER_SENTENCE_INLINE -->
<div class="deck">{{Deck}}</div>"""

def test_script_syntax():
    print("[*] Verifying JS Syntax in SENTENCE_BACK_TEMPLATE...")
    scripts = [part.split("</script>")[0] for part in SENTENCE_BACK_TEMPLATE.split("<script>") if "</script>" in part]
    for idx, sc in enumerate(scripts):
        tfile = f"/tmp/verify_sentence_back_{idx}.js"
        with open(tfile, "w") as f:
            f.write(sc)
        res = subprocess.run(["node", "--check", tfile], capture_output=True, text=True)
        if res.returncode != 0:
            print(f"[!] Syntax error in script #{idx}:")
            print(res.stderr)
            raise RuntimeError("Syntax check failed")
        print(f"  ✓ Script #{idx}: Syntax OK")

def apply_updates():
    from integrations.anki_connect import AnkiConnector
    from config import MODEL_SENTENCE, MODEL_GRAMMAR

    test_script_syntax()

    # 1. Update English Sentence
    print("\n[*] Updating 'English Sentence' templates via AnkiConnect...")
    s_templates = AnkiConnector.invoke("modelTemplates", modelName=MODEL_SENTENCE)
    if "Card 1" in s_templates:
        s_templates["Card 1"]["Back"] = SENTENCE_BACK_TEMPLATE
        AnkiConnector.update_model_templates(MODEL_SENTENCE, s_templates)
        print("  ✓ 'English Sentence' templates updated in Anki.")

    # 2. Update English Grammar (Card 3 uses SENTENCE_BACK_TEMPLATE, Card 1 clean)
    print("\n[*] Updating 'English Grammar' templates via AnkiConnect...")
    g_templates = AnkiConnector.invoke("modelTemplates", modelName=MODEL_GRAMMAR)
    if "Card 1" in g_templates:
        g_templates["Card 1"]["Back"] = re.sub(
            r"<!-- ANKI_LINK_MANAGER_SENTENCE.*?-->.*?<!-- /ANKI_LINK_MANAGER_SENTENCE.*?-->\n?",
            "",
            g_templates["Card 1"]["Back"],
            flags=re.DOTALL
        ).strip()
    if "Card 3" in g_templates:
        g_templates["Card 3"]["Back"] = SENTENCE_BACK_TEMPLATE
    AnkiConnector.update_model_templates(MODEL_GRAMMAR, g_templates)
    print("  ✓ 'English Grammar' templates updated in Anki.")

    # 3. Update data/design_config.json
    config_file = BASE_DIR / "data" / "design_config.json"
    if config_file.exists():
        with open(config_file, "r", encoding="utf-8") as f:
            design = json.load(f)
        if MODEL_SENTENCE in design and "templates" in design[MODEL_SENTENCE]:
            if "Card 1" in design[MODEL_SENTENCE]["templates"]:
                design[MODEL_SENTENCE]["templates"]["Card 1"]["Back"] = SENTENCE_BACK_TEMPLATE
        if MODEL_GRAMMAR in design and "templates" in design[MODEL_GRAMMAR]:
            design[MODEL_GRAMMAR]["templates"] = g_templates
        with open(config_file, "w", encoding="utf-8") as f:
            json.dump(design, f, ensure_ascii=False, indent=2)
        print("  ✓ data/design_config.json updated successfully.")

if __name__ == "__main__":
    apply_updates()
