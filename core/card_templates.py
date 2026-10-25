"""카드 뒷면 연결 표시 템플릿.

카드는 맥 Anki에서 보고, Anki Manager 백엔드는 서버(oracle-quant)에 있다.
맥에서 서버 백엔드로 가는 길은 SSH 터널(127.0.0.1:8011)뿐이라 카드도 이 주소로 묻는다.
(폰이나 터널이 닫힌 맥에서는 조용히 표시만 빠진다.)
"""
import re
from pathlib import Path

from config import MODEL_ZH_SENTENCE
from integrations.anki_connect import AnkiConnector

BADGE_BASE_URL = "http://127.0.0.1:8011"

_ZH_CORE = (Path(__file__).resolve().parent.parent / "scripts" / "zh_highlight_core.js").read_text(encoding="utf-8")
_ZH_CORE = _ZH_CORE.split('if (typeof module !== "undefined"')[0].strip()

ZH_MARK_START = "<!-- ANKI_LINK_MANAGER_ZH -->"
ZH_MARK_END = "<!-- /ANKI_LINK_MANAGER_ZH -->"
ZH_SPAN = '<span id="alm-zh-sentence-text">{{문장}}</span>'

ZH_BLOCK = ZH_MARK_START + """
<style>
.linked-word { color: #b91c1c; border-bottom: 1px dotted currentColor; cursor: help; }
.nightMode .linked-word, .night_mode .linked-word { color: #f87171; }
</style>
<script>
(function() {
""" + _ZH_CORE + """
  function apply() {
    var el = document.getElementById("alm-zh-sentence-text");
    if (!el || el.hasAttribute("data-linked-highlighted")) return;
    var text = (el.textContent || "").trim();
    if (!text) return;
    fetch(\"""" + BADGE_BASE_URL + """/api/links/badge/sentence?lang=zh&text=" + encodeURIComponent(text))
      .then(function(r) { return r.json(); })
      .then(function(d) {
        var html = zhHighlight(text, d && d.items);
        if (html === null) return;
        el.innerHTML = html;
        el.setAttribute("data-linked-highlighted", "true");
      })
      .catch(function() {});
  }
  apply();
  if (typeof onUpdateHook !== "undefined") { onUpdateHook.push(apply); }
})();
</script>
""" + ZH_MARK_END


def remove_zh_sentence_badge(back: str) -> str:
    """inject_zh_sentence_badge를 되돌린다."""
    back = re.sub(r"\n*" + re.escape(ZH_MARK_START) + r".*?" + re.escape(ZH_MARK_END), "", back, flags=re.DOTALL)
    return back.replace(ZH_SPAN, "{{문장}}")


def inject_zh_sentence_badge(back: str) -> str:
    """중국어 문장 뒷면의 {{문장}}을 표시용 span으로 감싸고 표시 블록을 끝에 한 번만 붙인다."""
    back = remove_zh_sentence_badge(back)
    return back.replace("{{문장}}", ZH_SPAN, 1) + "\n\n" + ZH_BLOCK


def apply_zh_sentence_badge() -> None:
    """Chinese Sentence 모델의 모든 카드 뒷면에 표시 블록을 넣는다 (앞면은 그대로)."""
    templates = AnkiConnector.invoke("modelTemplates", modelName=MODEL_ZH_SENTENCE)
    updated = {name: {"Front": t["Front"], "Back": inject_zh_sentence_badge(t["Back"])} for name, t in templates.items()}
    AnkiConnector.invoke("updateModelTemplates", model={"name": MODEL_ZH_SENTENCE, "templates": updated})


_OLD_BADGE = "http://127.0.0.1:8001/api/links/badge/"
_NEW_BADGE = BADGE_BASE_URL + "/api/links/badge/"


def retarget_badge_url(back: str) -> str:
    """서버 이전(2026-10-11) 전의 배지 주소(맥 로컬 8001)를 터널 주소로 바꾼다. 다른 부분은 건드리지 않는다."""
    return back.replace(_OLD_BADGE, _NEW_BADGE)


def apply_english_badge_url() -> None:
    """English Sentence·Grammar 템플릿 중 배지를 쓰는 카드의 주소만 바꾼다 (템플릿 전체를 덮어쓰지 않음)."""
    for model in ("English Sentence", "English Grammar"):
        templates = AnkiConnector.invoke("modelTemplates", modelName=model)
        updated = {name: {"Front": t["Front"], "Back": retarget_badge_url(t["Back"])} for name, t in templates.items()}
        if any(updated[n]["Back"] != templates[n]["Back"] for n in templates):
            AnkiConnector.invoke("updateModelTemplates", model={"name": model, "templates": updated})
