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
    tpls["카드 1"]["Front"] = swap_engine(tpls["카드 1"]["Front"], FRONT_BLOCK)
    tpls["카드 1"]["Back"] = swap_engine(tpls["카드 1"]["Back"], BACK_BLOCK)
    tpls["카드 2"]["Back"] = swap_engine(tpls["카드 2"]["Back"], BACK_BLOCK)
    for n, h in (("c1front", tpls["카드 1"]["Front"]), ("c1back", tpls["카드 1"]["Back"]), ("c2back", tpls["카드 2"]["Back"])):
        check_js(n, h)

    AnkiConnector.update_model_templates(MODEL_VOCAB, tpls)
    print("  Anki templates updated")

    cfg = BASE_DIR / "data" / "design_config.json"
    if cfg.exists():
        design = json.loads(cfg.read_text(encoding="utf-8"))
        if MODEL_VOCAB in design:
            design[MODEL_VOCAB]["templates"] = tpls
            cfg.write_text(json.dumps(design, ensure_ascii=False, indent=2), encoding="utf-8")
            print("  data/design_config.json updated")


if __name__ == "__main__":
    main()
