"""Coding Cloze 노트 타입·덱 생성 및 시드 카드 등록.

사용: python -m scripts.add_coding_seed [--url URL] [--dry-run]
기본 URL은 http://127.0.0.1:18765 (ssh -N -L 18765:127.0.0.1:8765 oracle-quant).
추가만 한다. 기존 노트·노트 타입은 수정하지 않는다.
"""

from __future__ import annotations

import argparse
import html
import json
import logging
import sys
from pathlib import Path
from typing import Any

import requests

logger = logging.getLogger("add_coding_seed")

MODEL_NAME = "Coding Cloze"
DECK_NAME = "2. Coding::2.1. Quant"
FIELDS = ["제목", "정답", "코드", "분류", "출처", "설명"]
SEED_PATH = Path(__file__).resolve().parent / "seeds" / "coding_seed_quant_36.json"

CSS = """
.card { font-family: '나눔고딕', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  font-size: 20px; font-weight: 600; text-align: center; color: #1f2937; background: #ffffff;
  border: 1px solid #e5e7eb; border-radius: 14px; width: min(94%, 760px); margin: 24px auto; padding: 22px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.05), 0 6px 12px rgba(0,0,0,0.08); }
@media (max-width: 1024px) { .card { width: 94%; font-size: 17px; padding: 16px; margin: 14px auto; } }
.card hr { border: none; border-top: 1px solid #e5e7eb; margin: 14px 0 18px; }
.title { font-size: 21px; font-weight: 700; margin-bottom: 12px; color: #111827; line-height: 1.45; }
.pos { display: inline-block; font-size: 13px; font-weight: 700; padding: 3px 10px; border-radius: 999px;
  border: 1px solid transparent; margin-left: 6px; vertical-align: middle; box-shadow: 0 1px 2px rgba(0,0,0,0.05); }
.v { background: #e7f3ff; color: #0b66c3; border-color: #b7d3fa; }
.n { background: #fffbe6; color: #8a6d00; border-color: #f2e3a3; }
.adj { background: #f3e9ff; color: #6a35c0; border-color: #d7c2fa; }
.idiom { background: #f3f4f6; color: #374151; border-color: #d1d5db; font-family: Menlo, Consolas, monospace; font-size: 12px; }
.example, .explain { background-color: #f1f3f5; color: #333; padding: 14px 16px; border-radius: 8px; margin-top: 12px;
  text-align: left; line-height: 1.6; border: 1px solid #e0e0e0; box-shadow: inset 0 1px 3px rgba(0,0,0,0.05); }
.explain { font-size: 17px; font-weight: 500; word-break: keep-all; }
.code-font { font-family: "SF Mono", Menlo, Consolas, monospace; font-size: 15px; line-height: 1.6;
  white-space: pre-wrap; word-break: break-word; margin: 0; font-weight: 500; }
.answer { font-family: "SF Mono", Menlo, Consolas, monospace; font-size: 20px; font-weight: 800; margin: 4px 0 10px; word-break: break-all; }
.cloze-blank { display: inline-block; font-family: "SF Mono", Menlo, Consolas, monospace; font-weight: 700;
  color: #0071e3; letter-spacing: 0.12em; padding: 0 2px; }
.example-highlight { color: #0071e3; font-weight: 700; text-decoration: underline; text-decoration-color: #0071e3; text-underline-offset: 3px; }
.tok-kw { color: #cf222e; font-weight: 700; } .tok-fn { color: #8250df; } .tok-mth { color: #0550ae; }
.tok-num { color: #0a3069; font-weight: 700; } .tok-str { color: #0c7a5b; } .tok-cmt { color: #6e7781; font-style: italic; }
.tok-op { color: #953800; } .tok-obj { color: #9a6700; }
.deck { text-align: right; font-size: 11px; color: #9ca3af; font-weight: 400; margin-top: 14px; }
.card.nightMode { background: #1f2937; color: #f3f4f6; border-color: #374151; }
.card.nightMode hr { border-top-color: #374151; }
.nightMode .title { color: #f9fafb; }
.nightMode .v { background: #1e3a8a; color: #bfdbfe; border-color: #1e40af; }
.nightMode .n { background: #78350f; color: #fde68a; border-color: #92400e; }
.nightMode .adj { background: #4c1d95; color: #ddd6fe; border-color: #5b21b6; }
.nightMode .idiom { background: #374151; color: #e5e7eb; border-color: #4b5563; }
.nightMode .example, .nightMode .explain { background-color: #374151; color: #f1f5f9; border-color: #4b5563; }
.nightMode .cloze-blank, .nightMode .example-highlight { color: #38bdf8; text-decoration-color: #38bdf8; }
.nightMode .tok-kw { color: #ff7b72; } .nightMode .tok-fn { color: #d2a8ff; } .nightMode .tok-mth { color: #79c0ff; }
.nightMode .tok-num { color: #a5d6ff; } .nightMode .tok-str { color: #7ee787; } .nightMode .tok-cmt { color: #8b949e; }
.nightMode .tok-op { color: #ffa657; } .nightMode .tok-obj { color: #f2cc60; }
.nightMode .deck { color: #6b7280; }
"""

# 앞·뒷면 공통 JS: 구문 강조, 분류 배지, 정답 구간 마스킹/강조
JS = r"""
<script>
(function () {
  var CAT = {pandas:"v", numpy:"v", guard:"n", design:"n", formula:"adj"};
  function esc(s){return s.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");}
  var RX = /(#[^\n]*)|("[^"]*"|'[^']*')|\b(def|return|if|else|elif|for|while|in|not|and|or|import|from|as|with|raise|True|False|None)\b|\b(pd|np|df|pos|held|equity|peak|drawdown|turnover|contrib|mask|self|stats|rng|view)\b|(\.[a-zA-Z_][a-zA-Z0-9_]*)(?=\s*\()|\b([a-zA-Z_][a-zA-Z0-9_]*)(?=\s*\()|\b(\d+(?:\.\d+)?)\b|(==|!=|<=|>=|<|>|=|\+|-|\*|\/)/g;
  var CLS = [null,"tok-cmt","tok-str","tok-kw","tok-obj","tok-mth","tok-fn","tok-num","tok-op"];
  function hl(code){
    var out="", last=0, m; RX.lastIndex=0;
    while((m=RX.exec(code))!==null){
      out+=esc(code.slice(last,m.index));
      for(var g=1;g<=8;g++){ if(m[g]!==undefined){ out+='<span class="'+CLS[g]+'">'+esc(m[g])+'</span>'; break; } }
      last=RX.lastIndex;
    }
    return out+esc(code.slice(last));
  }
  function txt(id){var e=document.getElementById(id); return e?e.textContent.replace(/\u00a0/g," "):"";}
  function render(){
    var code=txt("raw-code"), ans=txt("raw-ans").trim(), out=document.getElementById("code-out");
    if(!out) return;
    var i=code.indexOf(ans), mid;
    if(i<0){ out.innerHTML=hl(code); }
    else {
      var back=!!document.getElementById("is-back");
      mid = back ? '<span class="example-highlight">'+hl(ans)+'</span>' : '<span class="cloze-blank">_____</span>';
      out.innerHTML=hl(code.slice(0,i))+mid+hl(code.slice(i+ans.length));
    }
    var b=document.getElementById("cat-badge");
    if(b){ var c=(b.getAttribute("data-cat")||"").trim().toLowerCase(); b.className="pos "+(CAT[c]||"idiom"); b.textContent=c; }
  }
  render();
  if (typeof onUpdateHook !== "undefined") { onUpdateHook.push(render); }
})();
</script>
"""

FRONT = (
    '<div class="title">{{제목}} <span id="cat-badge" data-cat="{{분류}}"></span>'
    ' <span class="pos idiom">{{출처}}</span></div>\n'
    '<div class="example"><span id="raw-code" style="display:none">{{코드}}</span>'
    '<span id="raw-ans" style="display:none">{{정답}}</span>'
    '<pre id="code-out" class="code-font"></pre></div>\n'
    + JS + '<div class="deck">{{Deck}}</div>'
)

BACK = (
    '<span id="is-back" style="display:none"></span>\n'
    '<div class="title">{{제목}} <span id="cat-badge" data-cat="{{분류}}"></span>'
    ' <span class="pos idiom">{{출처}}</span></div>\n'
    '<div class="example"><span id="raw-code" style="display:none">{{코드}}</span>'
    '<span id="raw-ans" style="display:none">{{정답}}</span>'
    '<pre id="code-out" class="code-font"></pre></div>\n'
    '<hr>\n<div class="answer">{{정답}}</div>\n'
    '<div class="explain">{{설명}}</div>\n'
    + JS + '<div class="deck">{{Deck}}</div>'
)


def invoke(url: str, action: str, **params: Any) -> Any:
    resp = requests.post(url, json={"action": action, "version": 6, "params": params}, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    if data.get("error"):
        raise RuntimeError(f"{action}: {data['error']}")
    return data["result"]


def build_fields(card: dict[str, Any]) -> dict[str, str]:
    """코드·정답은 HTML 이스케이프해서 저장 (템플릿이 textContent로 읽는다)."""
    explain = (
        f"<b>① 원리</b> {html.escape(card['why'])}<br><br>"
        f"<b>② 누락·오류 시 버그</b> {html.escape(card['bug'])}"
    )
    return {
        "제목": html.escape(card["title"]),
        "정답": html.escape(card["answer"]),
        "코드": html.escape(card["code"]),
        "분류": card["category"],
        "출처": html.escape(card["source"]),
        "설명": explain,
    }


def validate(cards: list[dict[str, Any]]) -> None:
    ids = [c["id"] for c in cards]
    if len(set(ids)) != len(ids):
        raise ValueError("중복 id")
    for c in cards:
        if c["code"].count(c["answer"]) != 1:
            raise ValueError(f"카드 {c['id']}: 정답이 코드에 정확히 1회 있어야 함")


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:18765")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    cards = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    validate(cards)
    logger.info("시드 %d장 검증 통과", len(cards))
    if args.dry_run:
        return 0

    if MODEL_NAME not in invoke(args.url, "modelNames"):
        invoke(args.url, "createModel", modelName=MODEL_NAME, inOrderFields=FIELDS, css=CSS,
               isCloze=False, cardTemplates=[{"Name": "Card 1", "Front": FRONT, "Back": BACK}])
        logger.info("노트 타입 생성: %s", MODEL_NAME)
    invoke(args.url, "createDeck", deck=DECK_NAME)

    notes = [{"deckName": DECK_NAME, "modelName": MODEL_NAME, "fields": build_fields(c),
              "tags": ["coding", "quant", c["layer"].replace(" ", "_").lower()],
              "options": {"allowDuplicate": False}} for c in cards]
    ids = invoke(args.url, "addNotes", notes=notes)
    ok = sum(1 for i in ids if i)
    logger.info("등록 %d/%d (실패 %d)", ok, len(cards), len(cards) - ok)
    return 0 if ok == len(cards) else 1


if __name__ == "__main__":
    sys.exit(main())
