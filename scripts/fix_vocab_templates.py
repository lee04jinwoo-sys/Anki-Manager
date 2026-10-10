"""
Fix and verify English Vocabulary card templates for multi-example cloze/highlight.
Using raw strings (r\"\"\") to preserve all regex backslashes for JavaScript.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

os.environ["no_proxy"] = "*"
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

# -------------------------------------------------------------
# 1. Card 1 Front Template
# -------------------------------------------------------------
CARD1_FRONT = r"""<div class="title">
    {{뜻}} <span class="pos-raw" data-pos="{{품사}}"></span>
  </div>

  <div class="photo">{{사진}}</div>

  <!-- 예문 빈칸 박스 (동적 다중 예문 지원) -->
  <div class="example" id="cloze-example">
    <span id="cloze-raw-word" style="display:none;">{{단어}}</span>
    <span id="cloze-raw-sentence" style="display:none;">{{예문}}</span>
    <span id="cloze-display"></span>
  </div>

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

<!-- 문맥 Cloze 마스킹 엔진 v2 + 동적 랜덤 예문 선택 -->
<script>
(function() {
  function renderCloze() {
    var exampleBox = document.getElementById("cloze-example");
    var wordEl = document.getElementById("cloze-raw-word");
    var sentenceEl = document.getElementById("cloze-raw-sentence");
    var displayEl = document.getElementById("cloze-display");

    if (!exampleBox || !wordEl || !sentenceEl || !displayEl) return;
    if (exampleBox.hasAttribute("data-cloze-rendered")) return;

    function cleanHtml(str) {
      if (!str) return "";
      var tmp = document.createElement("div");
      tmp.innerHTML = str;
      return (tmp.textContent || tmp.innerText || "").trim();
    }

    var rawWord = cleanHtml(wordEl.innerHTML);
    var rawSent = cleanHtml(sentenceEl.innerHTML);

    if (!rawWord || !rawSent) {
      exampleBox.style.display = "none";
      return;
    }

    var sentences = rawSent.split("|||").map(function(s) { return s.trim(); }).filter(Boolean);
    if (sentences.length === 0) {
      exampleBox.style.display = "none";
      return;
    }

    var IRREGULARS = {
      "get": "(?:get|gets|getting|got|gotten)",
      "take": "(?:take|takes|taking|took|taken)",
      "make": "(?:make|makes|making|made)",
      "give": "(?:give|gives|giving|gave|given)",
      "come": "(?:come|comes|coming|came)",
      "go": "(?:go|goes|going|went|gone)",
      "see": "(?:see|sees|seeing|saw|seen)",
      "have": "(?:have|has|having|had)",
      "run": "(?:run|runs|running|ran)",
      "keep": "(?:keep|keeps|keeping|kept)",
      "find": "(?:find|finds|finding|found)",
      "fall": "(?:fall|falls|falling|fell|fallen)",
      "break": "(?:break|breaks|breaking|broke|broken)",
      "bring": "(?:bring|brings|bringing|brought)",
      "buy": "(?:buy|buys|buying|bought)",
      "catch": "(?:catch|catches|catching|caught)",
      "choose": "(?:choose|chooses|choosing|chose|chosen)",
      "do": "(?:do|does|doing|did|done)",
      "draw": "(?:draw|draws|drawing|drew|drawn)",
      "drive": "(?:drive|drives|driving|drove|driven)",
      "feel": "(?:feel|feels|feeling|felt)",
      "fly": "(?:fly|flies|flying|flew|flown)",
      "grow": "(?:grow|grows|growing|grew|grown)",
      "hear": "(?:hear|hears|hearing|heard)",
      "hold": "(?:hold|holds|holding|held)",
      "know": "(?:know|knows|knowing|knew|known)",
      "leave": "(?:leave|leaves|leaving|left)",
      "lose": "(?:lose|loses|losing|lost)",
      "pay": "(?:pay|pays|paying|paid)",
      "put": "(?:put|puts|putting)",
      "read": "(?:read|reads|reading)",
      "say": "(?:say|says|saying|said)",
      "send": "(?:send|sends|sending|sent)",
      "show": "(?:show|shows|showing|showed|shown)",
      "speak": "(?:speak|speaks|speaking|spoke|spoken)",
      "spend": "(?:spend|spends|spending|spent)",
      "stand": "(?:stand|stands|standing|stood)",
      "tell": "(?:tell|tells|telling|told)",
      "think": "(?:think|thinks|thinking|thought)",
      "wear": "(?:wear|wears|wearing|wore|worn)",
      "win": "(?:win|wins|winning|won)",
      "write": "(?:write|writes|writing|wrote|written)",
      "freeze": "(?:freeze|freezes|freezing|froze|frozen)",
      "throw": "(?:throw|throws|throwing|threw|thrown)",
      "lend": "(?:lend|lends|lending|lent)",
      "speed": "(?:speed|speeds|speeding|sped)",
      "swear": "(?:swear|swears|swearing|swore|sworn)",
      "bite": "(?:bite|bites|biting|bit|bitten)",
      "hide": "(?:hide|hides|hiding|hid|hidden)",
      "wake": "(?:wake|wakes|waking|woke|woken)",
      "strike": "(?:strike|strikes|striking|struck)",
      "be": "(?:be|is|are|was|were|am|been|being)"
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

    function buildMaskTag(matchedStr) {
      var parts = matchedStr.split(/\s+/);
      var maskedParts = parts.map(function(w, idx) {
        if (!w || w.length === 0) return w;
        if (idx === 0) {
          return w.charAt(0) + "_".repeat(Math.max(1, w.length - 1));
        } else {
          return "_".repeat(w.length);
        }
      });
      return '<span class="cloze-blank">' + maskedParts.join(" ") + '</span>';
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

    var rawTokens = rawWord.split(/[\s/]+/);
    var tokens = rawTokens.filter(function(t) {
      return !/^(someone|somebody|sb|something|sth|one's|oneself|A|B|C|V|V-ing|to)$/i.test(t);
    });
    if (tokens.length === 0) {
      tokens = rawTokens.filter(function(t) { return /^[a-zA-Z]+$/.test(t); });
    }
    if (tokens.length === 0) tokens = rawTokens;

    var patternParts = tokens.map(buildTokenPattern);
    var sep = "(?:\\s+[\\w$\\'\\\"]+){0,4}\\s+";
    var regex = new RegExp("\\b(" + patternParts.join(sep) + ")\\b", "i");

    function tryMask(targetSent) {
      var match = targetSent.match(regex);
      if (match) {
        return targetSent.replace(regex, function(m) { return buildMaskTag(m); });
      }
      for (var i = 0; i < tokens.length; i++) {
        var tok = tokens[i];
        if (tok.length >= 4) {
          var subRegex = new RegExp("\\b(" + buildTokenPattern(tok) + ")\\b", "i");
          if (subRegex.test(targetSent)) {
            return targetSent.replace(subRegex, function(m) { return buildMaskTag(m); });
          }
        }
      }
      return null;
    }

    var chosenIdx = 0;
    if (sentences.length > 1) {
      chosenIdx = Math.floor(Math.random() * sentences.length);
    }
    var chosenSentence = sentences[chosenIdx];
    var maskedHtml = tryMask(chosenSentence);

    if (!maskedHtml && sentences.length > 1) {
      for (var sIdx = 0; sIdx < sentences.length; sIdx++) {
        if (sIdx === chosenIdx) continue;
        var altMasked = tryMask(sentences[sIdx]);
        if (altMasked) {
          chosenIdx = sIdx;
          chosenSentence = sentences[sIdx];
          maskedHtml = altMasked;
          break;
        }
      }
    }

    if (maskedHtml) {
      displayEl.innerHTML = maskedHtml;
    } else {
      displayEl.innerHTML = chosenSentence;
    }

    try {
      sessionStorage.setItem("anki_cloze_word", rawWord);
      sessionStorage.setItem("anki_cloze_sentence", chosenSentence);
    } catch(e) {}

    exampleBox.setAttribute("data-cloze-rendered", "true");
  }

  renderCloze();
  if (typeof onUpdateHook !== "undefined") {
    onUpdateHook.push(renderCloze);
  }
})();
</script>
<div class="deck">{{Deck}}</div>"""

# -------------------------------------------------------------
# 2. Card 1 Back Template
# -------------------------------------------------------------
CARD1_BACK = r"""<script>
(function() {
  function trigger() {
    var c = document.querySelector(".card");
    if (c) { c.classList.remove("anim-ready"); void c.offsetWidth; c.classList.add("anim-ready"); }
  }
  if (typeof onUpdateHook !== "undefined") { onUpdateHook.push(trigger); } else { trigger(); }
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
<script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
<div class="title">
  {{뜻}} <span class="pos-raw" data-pos="{{품사}}"></span>
</div>
<div class="photo">{{사진}}</div>

<hr>
<div class="word">{{단어}} {{소리}}</div>

<!-- 동적 예문 표시 박스 (앞면 일치 동기화 + 다른 예문 아코디언) -->
<div class="example" id="back-example-box">
  <span id="back-raw-word" style="display:none;">{{단어}}</span>
  <span id="back-raw-sentence" style="display:none;">{{예문}}</span>
  <div id="back-primary-sentence"></div>
  <div id="back-sub-examples"></div>
</div>

<div class="explain">{{설명}}</div>

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
(function() {
  function renderBackExample() {
    var box = document.getElementById("back-example-box");
    var wordEl = document.getElementById("back-raw-word");
    var sentEl = document.getElementById("back-raw-sentence");
    var primaryEl = document.getElementById("back-primary-sentence");
    var subEl = document.getElementById("back-sub-examples");
    if (!box || !wordEl || !sentEl || !primaryEl) return;

    function cleanHtml(str) {
      if (!str) return "";
      var tmp = document.createElement("div");
      tmp.innerHTML = str;
      return (tmp.textContent || tmp.innerText || "").trim();
    }

    var rawWord = cleanHtml(wordEl.innerHTML);
    var rawSent = cleanHtml(sentEl.innerHTML);
    if (!rawSent) {
      box.style.display = "none";
      return;
    }

    var sentences = rawSent.split("|||").map(function(s) { return s.trim(); }).filter(Boolean);
    if (sentences.length === 0) {
      box.style.display = "none";
      return;
    }

    var IRREGULARS = {
      "get": "(?:get|gets|getting|got|gotten)",
      "take": "(?:take|takes|taking|took|taken)",
      "make": "(?:make|makes|making|made)",
      "give": "(?:give|gives|giving|gave|given)",
      "come": "(?:come|comes|coming|came)",
      "go": "(?:go|goes|going|went|gone)",
      "see": "(?:see|sees|seeing|saw|seen)",
      "have": "(?:have|has|having|had)",
      "run": "(?:run|runs|running|ran)",
      "keep": "(?:keep|keeps|keeping|kept)",
      "find": "(?:find|finds|finding|found)",
      "fall": "(?:fall|falls|falling|fell|fallen)",
      "break": "(?:break|breaks|breaking|broke|broken)",
      "bring": "(?:bring|brings|bringing|brought)",
      "buy": "(?:buy|buys|buying|bought)",
      "catch": "(?:catch|catches|catching|caught)",
      "choose": "(?:choose|chooses|choosing|chose|chosen)",
      "do": "(?:do|does|doing|did|done)",
      "draw": "(?:draw|draws|drawing|drew|drawn)",
      "drive": "(?:drive|drives|driving|drove|driven)",
      "feel": "(?:feel|feels|feeling|felt)",
      "fly": "(?:fly|flies|flying|flew|flown)",
      "grow": "(?:grow|grows|growing|grew|grown)",
      "hear": "(?:hear|hears|hearing|heard)",
      "hold": "(?:hold|holds|holding|held)",
      "know": "(?:know|knows|knowing|knew|known)",
      "leave": "(?:leave|leaves|leaving|left)",
      "lose": "(?:lose|loses|losing|lost)",
      "pay": "(?:pay|pays|paying|paid)",
      "put": "(?:put|puts|putting)",
      "read": "(?:read|reads|reading)",
      "say": "(?:say|says|saying|said)",
      "send": "(?:send|sends|sending|sent)",
      "show": "(?:show|shows|showing|showed|shown)",
      "speak": "(?:speak|speaks|speaking|spoke|spoken)",
      "spend": "(?:spend|spends|spending|spent)",
      "stand": "(?:stand|stands|standing|stood)",
      "tell": "(?:tell|tells|telling|told)",
      "think": "(?:think|thinks|thinking|thought)",
      "wear": "(?:wear|wears|wearing|wore|worn)",
      "win": "(?:win|wins|winning|won)",
      "write": "(?:write|writes|writing|wrote|written)",
      "freeze": "(?:freeze|freezes|freezing|froze|frozen)",
      "throw": "(?:throw|throws|throwing|threw|thrown)",
      "lend": "(?:lend|lends|lending|lent)",
      "speed": "(?:speed|speeds|speeding|sped)",
      "swear": "(?:swear|swears|swearing|swore|sworn)",
      "bite": "(?:bite|bites|biting|bit|bitten)",
      "hide": "(?:hide|hides|hiding|hid|hidden)",
      "wake": "(?:wake|wakes|waking|woke|woken)",
      "strike": "(?:strike|strikes|striking|struck)",
      "be": "(?:be|is|are|was|were|am|been|being)"
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

    function highlightText(text, word) {
      if (!text) return "";
      if (!word) return text;
      var rawTokens = word.split(/[\s/]+/);
      var tokens = rawTokens.filter(function(t) {
        return !/^(someone|somebody|sb|something|sth|one's|oneself|A|B|C|V|V-ing|to)$/i.test(t);
      });
      if (tokens.length === 0) tokens = rawTokens.filter(function(t) { return /^[a-zA-Z]+$/.test(t); });
      if (tokens.length === 0) tokens = rawTokens;

      var patternParts = tokens.map(buildTokenPattern);
      var sep = "(?:\\s+[\\w$\\'\\\"]+){0,4}\\s+";
      try {
        var regex = new RegExp("\\b(" + patternParts.join(sep) + ")\\b", "i");
        if (regex.test(text)) {
          return text.replace(regex, '<span class="example-highlight">$1</span>');
        }
        for (var i = 0; i < tokens.length; i++) {
          var tok = tokens[i];
          if (tok.length >= 4) {
            var subRegex = new RegExp("\\b(" + buildTokenPattern(tok) + ")\\b", "i");
            if (subRegex.test(text)) {
              return text.replace(subRegex, '<span class="example-highlight">$1</span>');
            }
          }
        }
      } catch(e) {}
      return text;
    }

    var chosen = sentences[0];
    try {
      var savedWord = sessionStorage.getItem("anki_cloze_word");
      var savedSent = sessionStorage.getItem("anki_cloze_sentence");
      if (savedWord === rawWord && savedSent && sentences.indexOf(savedSent) !== -1) {
        chosen = savedSent;
      }
    } catch(e) {}

    primaryEl.innerHTML = highlightText(chosen, rawWord);

    if (sentences.length > 1 && subEl) {
      var others = sentences.filter(function(s) { return s !== chosen; });
      if (others.length > 0) {
        var details = document.createElement("details");
        details.className = "more-examples";
        var summary = document.createElement("summary");
        summary.className = "more-examples-btn";
        summary.textContent = "다른 예문 보기 (" + others.length + "개)";
        var ul = document.createElement("ul");
        ul.className = "more-examples-list";
        others.forEach(function(s) {
          var li = document.createElement("li");
          li.innerHTML = highlightText(s, rawWord);
          ul.appendChild(li);
        });
        details.appendChild(summary);
        details.appendChild(ul);
        subEl.innerHTML = "";
        subEl.appendChild(details);
      } else {
        subEl.innerHTML = "";
      }
    } else if (subEl) {
      subEl.innerHTML = "";
    }
  }

  renderBackExample();
  if (typeof onUpdateHook !== "undefined") {
    onUpdateHook.push(renderBackExample);
  }
})();
</script>
<div class="deck">{{Deck}}</div>"""

# -------------------------------------------------------------
# 3. Card 2 Front Template
# -------------------------------------------------------------
CARD2_FRONT = r"""<div class="title">
    {{단어}}{{소리}} <span class="pos-raw" data-pos="{{품사}}"></span>
  </div>

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
<div class="deck">{{Deck}}</div>"""

# -------------------------------------------------------------
# 4. Card 2 Back Template
# -------------------------------------------------------------
CARD2_BACK = r"""<script>
(function() {
  function trigger() {
    var c = document.querySelector(".card");
    if (c) { c.classList.remove("anim-ready"); void c.offsetWidth; c.classList.add("anim-ready"); }
  }
  if (typeof onUpdateHook !== "undefined") { onUpdateHook.push(trigger); } else { trigger(); }
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
<script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
<div class="title">
  {{단어}} <span class="pos-raw" data-pos="{{품사}}"></span>
</div>
<div class="photo">{{사진}}</div>

<hr>
<div class="word">{{뜻}}</div>

<!-- 동적 예문 표시 박스 (대표 예문 + 다른 예문 아코디언) -->
<div class="example" id="back-example-box">
  <span id="back-raw-word" style="display:none;">{{단어}}</span>
  <span id="back-raw-sentence" style="display:none;">{{예문}}</span>
  <div id="back-primary-sentence"></div>
  <div id="back-sub-examples"></div>
</div>

<div class="explain">{{설명}}</div>

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
(function() {
  function renderBackExample() {
    var box = document.getElementById("back-example-box");
    var wordEl = document.getElementById("back-raw-word");
    var sentEl = document.getElementById("back-raw-sentence");
    var primaryEl = document.getElementById("back-primary-sentence");
    var subEl = document.getElementById("back-sub-examples");
    if (!box || !wordEl || !sentEl || !primaryEl) return;

    function cleanHtml(str) {
      if (!str) return "";
      var tmp = document.createElement("div");
      tmp.innerHTML = str;
      return (tmp.textContent || tmp.innerText || "").trim();
    }

    var rawWord = cleanHtml(wordEl.innerHTML);
    var rawSent = cleanHtml(sentEl.innerHTML);
    if (!rawSent) {
      box.style.display = "none";
      return;
    }

    var sentences = rawSent.split("|||").map(function(s) { return s.trim(); }).filter(Boolean);
    if (sentences.length === 0) {
      box.style.display = "none";
      return;
    }

    var IRREGULARS = {
      "get": "(?:get|gets|getting|got|gotten)",
      "take": "(?:take|takes|taking|took|taken)",
      "make": "(?:make|makes|making|made)",
      "give": "(?:give|gives|giving|gave|given)",
      "come": "(?:come|comes|coming|came)",
      "go": "(?:go|goes|going|went|gone)",
      "see": "(?:see|sees|seeing|saw|seen)",
      "have": "(?:have|has|having|had)",
      "run": "(?:run|runs|running|ran)",
      "keep": "(?:keep|keeps|keeping|kept)",
      "find": "(?:find|finds|finding|found)",
      "fall": "(?:fall|falls|falling|fell|fallen)",
      "break": "(?:break|breaks|breaking|broke|broken)",
      "bring": "(?:bring|brings|bringing|brought)",
      "buy": "(?:buy|buys|buying|bought)",
      "catch": "(?:catch|catches|catching|caught)",
      "choose": "(?:choose|chooses|choosing|chose|chosen)",
      "do": "(?:do|does|doing|did|done)",
      "draw": "(?:draw|draws|drawing|drew|drawn)",
      "drive": "(?:drive|drives|driving|drove|driven)",
      "feel": "(?:feel|feels|feeling|felt)",
      "fly": "(?:fly|flies|flying|flew|flown)",
      "grow": "(?:grow|grows|growing|grew|grown)",
      "hear": "(?:hear|hears|hearing|heard)",
      "hold": "(?:hold|holds|holding|held)",
      "know": "(?:know|knows|knowing|knew|known)",
      "leave": "(?:leave|leaves|leaving|left)",
      "lose": "(?:lose|loses|losing|lost)",
      "pay": "(?:pay|pays|paying|paid)",
      "put": "(?:put|puts|putting)",
      "read": "(?:read|reads|reading)",
      "say": "(?:say|says|saying|said)",
      "send": "(?:send|sends|sending|sent)",
      "show": "(?:show|shows|showing|showed|shown)",
      "speak": "(?:speak|speaks|speaking|spoke|spoken)",
      "spend": "(?:spend|spends|spending|spent)",
      "stand": "(?:stand|stands|standing|stood)",
      "tell": "(?:tell|tells|telling|told)",
      "think": "(?:think|thinks|thinking|thought)",
      "wear": "(?:wear|wears|wearing|wore|worn)",
      "win": "(?:win|wins|winning|won)",
      "write": "(?:write|writes|writing|wrote|written)",
      "freeze": "(?:freeze|freezes|freezing|froze|frozen)",
      "throw": "(?:throw|throws|throwing|threw|thrown)",
      "lend": "(?:lend|lends|lending|lent)",
      "speed": "(?:speed|speeds|speeding|sped)",
      "swear": "(?:swear|swears|swearing|swore|sworn)",
      "bite": "(?:bite|bites|biting|bit|bitten)",
      "hide": "(?:hide|hides|hiding|hid|hidden)",
      "wake": "(?:wake|wakes|waking|woke|woken)",
      "strike": "(?:strike|strikes|striking|struck)",
      "be": "(?:be|is|are|was|were|am|been|being)"
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

    function highlightText(text, word) {
      if (!text) return "";
      if (!word) return text;
      var rawTokens = word.split(/[\s/]+/);
      var tokens = rawTokens.filter(function(t) {
        return !/^(someone|somebody|sb|something|sth|one's|oneself|A|B|C|V|V-ing|to)$/i.test(t);
      });
      if (tokens.length === 0) tokens = rawTokens.filter(function(t) { return /^[a-zA-Z]+$/.test(t); });
      if (tokens.length === 0) tokens = rawTokens;

      var patternParts = tokens.map(buildTokenPattern);
      var sep = "(?:\\s+[\\w$\\'\\\"]+){0,4}\\s+";
      try {
        var regex = new RegExp("\\b(" + patternParts.join(sep) + ")\\b", "i");
        if (regex.test(text)) {
          return text.replace(regex, '<span class="example-highlight">$1</span>');
        }
        for (var i = 0; i < tokens.length; i++) {
          var tok = tokens[i];
          if (tok.length >= 4) {
            var subRegex = new RegExp("\\b(" + buildTokenPattern(tok) + ")\\b", "i");
            if (subRegex.test(text)) {
              return text.replace(subRegex, '<span class="example-highlight">$1</span>');
            }
          }
        }
      } catch(e) {}
      return text;
    }

    var chosen = sentences[0];
    primaryEl.innerHTML = highlightText(chosen, rawWord);

    if (sentences.length > 1 && subEl) {
      var others = sentences.filter(function(s) { return s !== chosen; });
      if (others.length > 0) {
        var details = document.createElement("details");
        details.className = "more-examples";
        var summary = document.createElement("summary");
        summary.className = "more-examples-btn";
        summary.textContent = "다른 예문 보기 (" + others.length + "개)";
        var ul = document.createElement("ul");
        ul.className = "more-examples-list";
        others.forEach(function(s) {
          var li = document.createElement("li");
          li.innerHTML = highlightText(s, rawWord);
          ul.appendChild(li);
        });
        details.appendChild(summary);
        details.appendChild(ul);
        subEl.innerHTML = "";
        subEl.appendChild(details);
      } else {
        subEl.innerHTML = "";
      }
    } else if (subEl) {
      subEl.innerHTML = "";
    }
  }

  renderBackExample();
  if (typeof onUpdateHook !== "undefined") {
    onUpdateHook.push(renderBackExample);
  }
})();
</script>
<div class="deck">{{Deck}}</div>"""

def verify_all_templates():
    print("[*] Verifying JS Syntax for all templates using node --check...")
    templates = {
        "Card 1 Front": CARD1_FRONT,
        "Card 1 Back": CARD1_BACK,
        "Card 2 Front": CARD2_FRONT,
        "Card 2 Back": CARD2_BACK,
    }
    for name, html in templates.items():
        scripts = [part.split("</script>")[0] for part in html.split("<script>") if "</script>" in part]
        for idx, sc in enumerate(scripts):
            tfile = f"/tmp/verify_{name.replace(' ', '_')}_{idx}.js"
            with open(tfile, "w") as f:
                f.write(sc)
            res = subprocess.run(["node", "--check", tfile], capture_output=True, text=True)
            if res.returncode != 0:
                print(f"[!] Syntax error in {name} script #{idx}:")
                print(res.stderr)
                raise RuntimeError(f"Syntax error in {name}")
            else:
                print(f"  ✓ {name} script #{idx}: Syntax OK")

def apply_to_anki_and_config():
    from integrations.anki_connect import AnkiConnector
    from config import MODEL_VOCAB

    verify_all_templates()

    print("\n[*] Updating Anki Model Templates via AnkiConnect...")
    new_templates = {
        "카드 1": {
            "Front": CARD1_FRONT,
            "Back": CARD1_BACK
        },
        "카드 2": {
            "Front": CARD2_FRONT,
            "Back": CARD2_BACK
        }
    }
    AnkiConnector.update_model_templates(MODEL_VOCAB, new_templates)
    print("  ✓ AnkiConnect templates updated successfully.")

    config_file = BASE_DIR / "data" / "design_config.json"
    if config_file.exists():
        with open(config_file, "r", encoding="utf-8") as f:
            design = json.load(f)
        if MODEL_VOCAB in design:
            design[MODEL_VOCAB]["templates"] = new_templates
            with open(config_file, "w", encoding="utf-8") as f:
                json.dump(design, f, ensure_ascii=False, indent=2)
            print("  ✓ data/design_config.json updated successfully.")

if __name__ == "__main__":
    apply_to_anki_and_config()
