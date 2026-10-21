"""
Deploy the rule-based cloze/highlight engine (scripts/cloze_core.js) into the
English Vocabulary note-type templates. Only the engine <script> blocks are replaced;
title / POS badge / animation parts of the templates are left untouched.
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

CORE_JS = (BASE_DIR / "scripts" / "cloze_core.js").read_text(encoding="utf-8")

# Anki template syntax uses {{ }}; the core JS must not contain it.
assert "{{" not in CORE_JS and "}}" not in CORE_JS, "core JS contains template braces"

FRONT_BLOCK = (
    '<script id="cloze-engine">\n'
    + CORE_JS
    + r"""
(function () {
  function esc(s) {
    return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }
  function renderCloze() {
    var box = document.getElementById("cloze-example");
    var wordEl = document.getElementById("cloze-raw-word");
    var sentEl = document.getElementById("cloze-raw-sentence");
    var disp = document.getElementById("cloze-display");
    if (!box || !wordEl || !sentEl || !disp) return;
    if (box.hasAttribute("data-cloze-rendered")) return;
    var word = clozeNormalize(wordEl.innerHTML);
    var sentences = clozeSplitSentences(sentEl.innerHTML);
    if (!word || !sentences.length) { box.style.display = "none"; return; }
    var res = clozeFront(sentences, word);
    disp.innerHTML = res.html !== null ? res.html : esc(res.sentence);
    try {
      sessionStorage.setItem("anki_cloze_word", word);
      sessionStorage.setItem("anki_cloze_sentence", res.sentence);
    } catch (e) {}
    box.setAttribute("data-cloze-rendered", "true");
  }
  renderCloze();
  if (typeof onUpdateHook !== "undefined") { onUpdateHook.push(renderCloze); }
})();
</script>"""
)

BACK_BLOCK = (
    '<script id="cloze-engine">\n'
    + CORE_JS
    + r"""
(function () {
  function esc(s) {
    return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }
  function renderBack() {
    var box = document.getElementById("back-example-box");
    var wordEl = document.getElementById("back-raw-word");
    var sentEl = document.getElementById("back-raw-sentence");
    var out = document.getElementById("back-primary-sentence");
    if (!box || !wordEl || !sentEl || !out) return;
    var word = clozeNormalize(wordEl.innerHTML);
    var sentences = clozeSplitSentences(sentEl.innerHTML);
    if (!sentences.length) { box.style.display = "none"; return; }
    var saved = null;
    try {
      if (sessionStorage.getItem("anki_cloze_word") === word) {
        saved = sessionStorage.getItem("anki_cloze_sentence");
      }
    } catch (e) {}
    var res = clozeBack(sentences, word, saved);
    out.innerHTML = res.html !== null ? res.html : esc(res.sentence);
  }
  renderBack();
  if (typeof onUpdateHook !== "undefined") { onUpdateHook.push(renderBack); }
})();
</script>"""
)

OLD_ENGINE_RGX = re.compile(
    r"<script(?: id=\"cloze-engine\")?>(?:(?!</script>).)*?"
    r"(?:function renderCloze|function renderBackExample|function renderBack\b)"
    r".*?</script>",
    re.DOTALL,
)


def swap_engine(html: str, block: str) -> str:
    matches = OLD_ENGINE_RGX.findall(html)
    if len(matches) != 1:
        raise RuntimeError(f"expected exactly 1 engine block, found {len(matches)}")
    return OLD_ENGINE_RGX.sub(lambda _m: block, html, count=1)


POS_AND_TIER_SCRIPT = r"""<script>
(function(){
  document.querySelectorAll(".title, .word").forEach(function(el){
    for (var i = 0; i < el.childNodes.length; i++) {
      var n = el.childNodes[i];
      if (n.nodeType === 3) {
        n.nodeValue = n.nodeValue.replace(/\s*\/\s*/g, ", ");
      }
    }
  });
  var TIER_MAP = {
    "freq::tier1_essential": ["필수", "tier-1"],
    "freq::tier2_common": ["상용", "tier-2"],
    "freq::tier3_advanced": ["고급", "tier-3"],
    "freq::tier4_academic": ["학술", "tier-4"],
    "freq::tier5_rare": ["희귀", "tier-5"]
  };
  document.querySelectorAll(".pos-raw").forEach(function(el){
    var raw=el.getAttribute("data-pos")||"";
    var tagsRaw=el.getAttribute("data-tags")||"";
    var parts=raw.split(",").map(function(s){return s.trim();}).filter(Boolean);
    var g=document.createElement("span");
    g.style.cssText="display:inline-flex;gap:4px;margin-left:6px;vertical-align:middle;";
    parts.forEach(function(p){
      var norm = p.trim().toLowerCase();
      var label = p.trim();
      if (/phr|collocation/i.test(norm)) {
        label = "idiom";
        norm = "idiom";
      }
      var b=document.createElement("span");
      var cls=norm.replace(/[^a-z]/g,"");
      b.className="pos "+( cls||"");
      b.textContent=label;
      g.appendChild(b);
    });
    var tags = tagsRaw.split(/\s+/).filter(Boolean);
    for (var i = 0; i < tags.length; i++) {
      var info = TIER_MAP[tags[i]];
      if (info) {
        var tb = document.createElement("span");
        tb.className = "tier-badge " + info[1];
        tb.textContent = info[0];
        g.appendChild(tb);
        break;
      }
    }
    el.parentNode.replaceChild(g,el);
  });
})();
</script>"""

TIER_CSS_BLOCK = """/* --- 빈도 등급(Frequency Tier) 뱃지 스타일 --- */
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
.tier-4 { background: #f8fafc; color: #475569; border-color: #cbd5e1; }
.tier-5 { background: #f3f4f6; color: #6b7280; border-color: #d1d5db; }

@media (prefers-color-scheme: dark) {
  .tier-1 { background: #1e3a8a; color: #93c5fd; border-color: #2563eb; }
  .tier-2 { background: #0c4a6e; color: #7dd3fc; border-color: #0284c7; }
  .tier-3 { background: #312e81; color: #a5b4fc; border-color: #4f46e5; }
  .tier-4 { background: #1e293b; color: #94a3b8; border-color: #334155; }
  .tier-5 { background: #27272a; color: #a1a1aa; border-color: #3f3f46; }
}
.card.nightMode .tier-1 { background: #1e3a8a; color: #93c5fd; border-color: #2563eb; }
.card.nightMode .tier-2 { background: #0c4a6e; color: #7dd3fc; border-color: #0284c7; }
.card.nightMode .tier-3 { background: #312e81; color: #a5b4fc; border-color: #4f46e5; }
.card.nightMode .tier-4 { background: #1e293b; color: #94a3b8; border-color: #334155; }
.card.nightMode .tier-5 { background: #27272a; color: #a1a1aa; border-color: #3f3f46; }
"""

POS_SPAN_RGX = re.compile(r'<span class="pos-raw" data-pos="\{\{품사\}\}"[^>]*></span>')
POS_SCRIPT_RGX = re.compile(
    r"<script>\s*\(function\(\)\{[\s\S]*?document\.querySelectorAll\(\"\.pos-raw\"\)[\s\S]*?\}\)\(\);\s*</script>"
)


def apply_pos_and_tier(html: str) -> str:
    html = POS_SPAN_RGX.sub('<span class="pos-raw" data-pos="{{품사}}" data-tags="{{Tags}}"></span>', html)
    matches = POS_SCRIPT_RGX.findall(html)
    if len(matches) != 1:
        raise RuntimeError(f"expected exactly 1 pos-raw script block, found {len(matches)}")
    return POS_SCRIPT_RGX.sub(lambda _m: POS_AND_TIER_SCRIPT, html, count=1)


def ensure_tier_css(css: str) -> str:
    cleaned = re.sub(r"/\* --- 빈도 등급\(Frequency Tier\) 뱃지 스타일 --- \*/[\s\S]*?\.card\.nightMode \.tier-5 \{[^\n]+\}\n?", "", css)
    return cleaned.rstrip() + "\n\n" + TIER_CSS_BLOCK + "\n"


def check_js(name: str, html: str) -> None:
    scripts = [p.split("</script>")[0] for p in re.split(r"<script[^>]*>", html)[1:] if "</script>" in p]
    for i, sc in enumerate(scripts):
        tf = Path(f"/tmp/chk_{name.replace(' ', '_')}_{i}.js")
        tf.write_text(sc, encoding="utf-8")
        res = subprocess.run(["node", "--check", str(tf)], capture_output=True, text=True)
        if res.returncode != 0:
            raise RuntimeError(f"JS syntax error in {name} #{i}: {res.stderr}")
    print(f"  OK {name}: {len(scripts)} scripts")


def main() -> None:
    from config import MODEL_VOCAB
    from integrations.anki_connect import AnkiConnector

    tpls = AnkiConnector.invoke("modelTemplates", modelName=MODEL_VOCAB)
    tpls["카드 1"]["Front"] = apply_pos_and_tier(swap_engine(tpls["카드 1"]["Front"], FRONT_BLOCK))
    tpls["카드 1"]["Back"] = apply_pos_and_tier(swap_engine(tpls["카드 1"]["Back"], BACK_BLOCK))
    tpls["카드 2"]["Front"] = apply_pos_and_tier(tpls["카드 2"]["Front"])
    tpls["카드 2"]["Back"] = apply_pos_and_tier(swap_engine(tpls["카드 2"]["Back"], BACK_BLOCK))
    for n, h in (
        ("c1front", tpls["카드 1"]["Front"]),
        ("c1back", tpls["카드 1"]["Back"]),
        ("c2front", tpls["카드 2"]["Front"]),
        ("c2back", tpls["카드 2"]["Back"]),
    ):
        check_js(n, h)

    styling = AnkiConnector.invoke("modelStyling", modelName=MODEL_VOCAB)["css"]
    updated_css = ensure_tier_css(styling)

    AnkiConnector.update_model_templates(MODEL_VOCAB, tpls)
    AnkiConnector.update_model_styling(MODEL_VOCAB, updated_css)
    print("  Anki templates and CSS updated")

    cfg = BASE_DIR / "data" / "design_config.json"
    if cfg.exists():
        design = json.loads(cfg.read_text(encoding="utf-8"))
        if MODEL_VOCAB in design:
            design[MODEL_VOCAB]["templates"] = tpls
            design[MODEL_VOCAB]["css"] = updated_css
            cfg.write_text(json.dumps(design, ensure_ascii=False, indent=2), encoding="utf-8")
            print("  data/design_config.json updated")


if __name__ == "__main__":
    main()
