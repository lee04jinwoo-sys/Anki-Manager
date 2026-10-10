"""
Upgrade Cloze and Highlight engine to handle placeholder arguments, interchangeable determiners, and token-level gaps.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

os.environ["no_proxy"] = "*"
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

VOCAB_CARD1_FRONT = r"""<div class="title">
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
  document.querySelectorAll(".title, .word").forEach(function(el){
    for (var i = 0; i < el.childNodes.length; i++) {
      var n = el.childNodes[i];
      if (n.nodeType === 3) {
        n.nodeValue = n.nodeValue.replace(/\s*\/\s*/g, ", ");
      }
    }
  });
  document.querySelectorAll(".pos-raw").forEach(function(el){
    var raw=el.getAttribute("data-pos")||"";
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
    el.parentNode.replaceChild(g,el);
  });
})();
</script>


<!-- 문맥 Cloze 마스킹 엔진 v5: 완전한 불규칙/어미/변수/수식어 대응 -->
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
      var txt = (tmp.textContent || tmp.innerText || "").trim();
      return txt.replace(/[\u2018\u2019]/g, "'").replace(/[\u201C\u201D]/g, '"');
    }

    var rawWord = cleanHtml(wordEl.innerHTML);
    var rawSent = cleanHtml(sentenceEl.innerHTML);

    if (!rawWord || !rawSent) {
      exampleBox.style.display = "none";
      return;
    }

    var sentences = rawSent.split("|||").map(function(s) { 
      var cleaned = s.replace(/<[^>]+>/g, " ").trim();
      cleaned = cleaned.replace(/\([^)]*[\uac00-\ud7a3][^)]*\)/g, "").trim();
      cleaned = cleaned.replace(/^\d+\.\s*/, "").trim();
      return cleaned;
    }).filter(Boolean);

    if (sentences.length === 0) {
      exampleBox.style.display = "none";
      return;
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
      "win": "(?:win|wins|winning|won)", "write": "(?:write|writes|writing|wrote|written)",
      "freeze": "(?:freeze|freezes|freezing|froze|frozen)", "throw": "(?:throw|throws|throwing|threw|thrown)",
      "lend": "(?:lend|lends|lending|lent)", "speed": "(?:speed|speeds|speeding|sped)",
      "swear": "(?:swear|swears|swearing|swore|sworn)", "bite": "(?:bite|bites|biting|bit|bitten)",
      "hide": "(?:hide|hides|hiding|hid|hidden)", "wake": "(?:wake|wakes|wakeing|woke|woken)",
      "strike": "(?:strike|strikes|striking|struck)", "be": "(?:be|is|are|was|were|am|been|being)", "is": "(?:be|is|are|was|were|am|been|being)", "are": "(?:be|is|are|was|were|am|been|being)", "was": "(?:be|is|are|was|were|am|been|being)", "were": "(?:be|is|are|was|were|am|been|being)", "am": "(?:be|is|are|was|were|am|been|being)",
      "steal": "(?:steal|steals|stealing|stole|stolen)", "shake": "(?:shake|shakes|shaking|shook|shaken)",
      "blow": "(?:blow|blows|blowing|blew|blown)", "forget": "(?:forget|forgets|forgetting|forgot|forgotten)",
      "forgive": "(?:forgive|forgives|forgiving|forgave|forgiven)", "tear": "(?:tear|tears|tearing|tore|torn)",
      "bear": "(?:bear|bears|bearing|bore|born|borne)", "ride": "(?:ride|rides|riding|rode|ridden)",
      "rise": "(?:rise|rises|rising|rose|risen)", "arise": "(?:arise|arises|arising|arose|arisen)",
      "sink": "(?:sink|sinks|sinking|sank|sunk)", "shrink": "(?:shrink|shrinks|shrinking|shrank|shrunk)",
      "spin": "(?:spin|spins|spinning|spun)", "swing": "(?:swing|swings|swinging|swung)",
      "bind": "(?:bind|binds|binding|bound)", "feed": "(?:feed|feeds|feeding|fed)",
      "flee": "(?:flee|flees|fleeing|fled)", "sweep": "(?:sweep|sweeps|sweeping|swept)",
      "stick": "(?:stick|sticks|sticking|stuck)", "dig": "(?:dig|digs|digging|dug)",
      "bleed": "(?:bleed|bleeds|bleeding|bled)", "breed": "(?:breed|breeds|breeding|bred)",
      "kneel": "(?:kneel|kneels|kneeling|knelt)", "creep": "(?:creep|creeps|creeping|crept)",
      "weep": "(?:weep|weeps|weeping|wept)", "cling": "(?:cling|clings|clinging|clung)",
      "fling": "(?:fling|flings|flinging|flung)", "sting": "(?:sting|stings|stinging|stung)",
      "string": "(?:string|strings|stringing|strung)", "wring": "(?:wring|wrings|wringing|wrung)",
      "spit": "(?:spit|spits|spitting|spat)", "spill": "(?:spill|spills|spilling|spilt|spilled)",
      "leap": "(?:leap|leaps|leaping|leapt|leaped)", "bid": "(?:bid|bids|bidding)",
      "forbid": "(?:forbid|forbids|forbidding|forbade|forbidden)",
      "undergo": "(?:undergo|undergoes|undergoing|underwent|undergone)",
      "undertake": "(?:undertake|undertakes|undertaking|undertook|undertaken)",
      "overcome": "(?:overcome|overcomes|overcoming|overcame)",
      "withdraw": "(?:withdraw|withdraws|withdrawing|withdrew|withdrawn)",
      "withhold": "(?:withhold|withholds|withholding|withheld)",
      "uphold": "(?:uphold|upholds|upholding|upheld)"
    };

    function escapeRegex(s) {
      var specials = ".*+?^${}()|[]/\\-";
      var out = "";
      for (var i = 0; i < s.length; i++) {
        var c = s.charAt(i);
        out += (specials.indexOf(c) !== -1 ? "\\" : "") + c;
      }
      return out;
    }

    function buildTokenPattern(tok) {
      var tLower = tok.toLowerCase();
      if (/^(a|an|the)$/i.test(tLower)) {
        return "(?:a|an|the|this|that|these|those|my|your|his|her|its|our|their|some|any|no)";
      }
      if (IRREGULARS[tLower]) return IRREGULARS[tLower];
      var clean = escapeRegex(tLower);
      if (clean.length > 2 && clean.endsWith("y")) {
        var root = clean.slice(0, -1);
        return root + "(?:y|ies|ied|ying|[a-zA-Z]*)";
      }
      var stem = clean;
      if (stem.length > 3 && (stem.endsWith("e") || stem.endsWith("y"))) {
        stem = stem.slice(0, -1);
      }
      return stem + "[a-zA-Z]*";
    }

    function isPlaceholderToken(t) {
      var c = t.replace(/^[(\[{'\"’]+|[)\]}'\"’]+$/g, "");
      if (/^[ABCXY](?:['’]s)?$/.test(c)) return true;
      if (/^(someone|somebody|sb|something|sth|sb['’]s|sth['’]s|one['’]s|oneself|V|V-ing|v-ing|V-ed|v-ed)$/i.test(c)) return true;
      return false;
    }

    function parseWordChunks(word) {
      var cleanW = (word || "").replace(/<[^>]+>/g, " ").trim();
      var rawTokens = cleanW.split(/[\s/]+/);
      var chunks = [];
      var current = [];
      for (var i = 0; i < rawTokens.length; i++) {
        var tok = rawTokens[i];
        if (isPlaceholderToken(tok)) {
          if (current.length > 0) {
            chunks.push(current);
            current = [];
          }
        } else {
          var cleanTok = tok.replace(/^[^\w]+|[^\w]+$/g, "");
          if (cleanTok) current.push(cleanTok);
        }
      }
      if (current.length > 0) chunks.push(current);
      return chunks;
    }

    function buildChunkPatternPart(chunkTokens) {
      var patternParts = [];
      for (var i = 0; i < chunkTokens.length; i++) {
        if (i > 0) {
          patternParts.push("([,\\x27\\\"]*\\s+(?:[\\w$\\x27\\\",]+\\s+){0,2})");
        }
        patternParts.push("\\b(" + buildTokenPattern(chunkTokens[i]) + ")\\b");
      }
      return patternParts.join("");
    }

    function buildMaskTag(w, isHint) {
      if (!w) return "";
      if (isHint) {
        if (w.length === 1) return w;
        return '<span class="cloze-blank">' + w.charAt(0) + "_".repeat(Math.max(1, w.length - 1)) + '</span>';
      } else {
        return '<span class="cloze-blank">' + "_".repeat(w.length) + '</span>';
      }
    }

    function renderMaskedChunk(m, gIdx, chunkTokens) {
      var hintIdx = 0;
      while (hintIdx < chunkTokens.length - 1 && /^(a|an|the)$/i.test(chunkTokens[hintIdx])) {
        hintIdx++;
      }
      var out = "";
      for (var i = 0; i < chunkTokens.length; i++) {
        if (i > 0) out += m[gIdx++];
        var word = m[gIdx++];
        var isArticle = /^(a|an|the)$/i.test(chunkTokens[i]);
        if (isArticle) {
          out += word;
        } else if (i === hintIdx) {
          out += buildMaskTag(word, true);
        } else {
          out += buildMaskTag(word, false);
        }
      }
      return { out: out, gIdx: gIdx };
    }

    function tryMaskSentence(targetSent, word) {
      var chunks = parseWordChunks(word);
      if (chunks.length === 0) chunks = [word.split(/[\s/]+/)];

      var gapPattern = "(\s+[^.?!;]{0,60}?\s*)";

      if (chunks.length === 1) {
        var pat = buildChunkPatternPart(chunks[0]);
        var rgx1 = new RegExp(pat, "i");
        var m = rgx1.exec(targetSent);
        if (m) {
          var out = targetSent.slice(0, m.index);
          var res0 = renderMaskedChunk(m, 1, chunks[0]);
          out += res0.out + targetSent.slice(m.index + m[0].length);
          return out;
        }
        for (var tIdx = 0; tIdx < chunks[0].length; tIdx++) {
          var tok = chunks[0][tIdx];
          if (tok.length >= 4 && !/^(a|an|the)$/i.test(tok)) {
            var subRgx = new RegExp("\\b(" + buildTokenPattern(tok) + ")\\b", "i");
            var subM = subRgx.exec(targetSent);
            if (subM) {
              return targetSent.slice(0, subM.index) + buildMaskTag(subM[1], true) + targetSent.slice(subM.index + subM[0].length);
            }
          }
        }
      } else if (chunks.length === 2) {
        var p0 = buildChunkPatternPart(chunks[0]);
        var p1 = buildChunkPatternPart(chunks[1]);
        var rgx2 = new RegExp(p0 + gapPattern + p1, "i");
        var m = rgx2.exec(targetSent);
        if (m) {
          var out = targetSent.slice(0, m.index);
          var res0 = renderMaskedChunk(m, 1, chunks[0]);
          out += res0.out + m[res0.gIdx++];
          var res1 = renderMaskedChunk(m, res0.gIdx, chunks[1]);
          out += res1.out + targetSent.slice(m.index + m[0].length);
          return out;
        }
        // Fallback: match chunk 0 alone
        var pat0 = buildChunkPatternPart(chunks[0]);
        var rgxFallback = new RegExp(pat0, "i");
        var mFb = rgxFallback.exec(targetSent);
        if (mFb) {
          var out = targetSent.slice(0, mFb.index);
          var resFb = renderMaskedChunk(mFb, 1, chunks[0]);
          out += resFb.out + targetSent.slice(mFb.index + mFb[0].length);
          return out;
        }
      } else if (chunks.length >= 3) {
        var p0 = buildChunkPatternPart(chunks[0]);
        var p1 = buildChunkPatternPart(chunks[1]);
        var p2 = buildChunkPatternPart(chunks[2]);
        var rgx3 = new RegExp(p0 + gapPattern + p1 + gapPattern + p2, "i");
        var m = rgx3.exec(targetSent);
        if (m) {
          var out = targetSent.slice(0, m.index);
          var res0 = renderMaskedChunk(m, 1, chunks[0]);
          out += res0.out + m[res0.gIdx++];
          var res1 = renderMaskedChunk(m, res0.gIdx, chunks[1]);
          out += res1.out + m[res1.gIdx++];
          var res2 = renderMaskedChunk(m, res1.gIdx, chunks[2]);
          out += res2.out + targetSent.slice(m.index + m[0].length);
          return out;
        }
      }
      return null;
    }

    var chosenIdx = 0;
    if (sentences.length > 1) {
      chosenIdx = Math.floor(Math.random() * sentences.length);
    }
    var chosenSentence = sentences[chosenIdx];
    var maskedHtml = tryMaskSentence(chosenSentence, rawWord);

    if (!maskedHtml && sentences.length > 1) {
      for (var sIdx = 0; sIdx < sentences.length; sIdx++) {
        if (sIdx === chosenIdx) continue;
        var altMasked = tryMaskSentence(sentences[sIdx], rawWord);
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

VOCAB_CARD1_BACK = r"""<script>
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

<!-- 예문 표시 박스 (앞면 일치 동기화 + 하이라이트) -->
<div class="example" id="back-example-box">
  <span id="back-raw-word" style="display:none;">{{단어}}</span>
  <span id="back-raw-sentence" style="display:none;">{{예문}}</span>
  <div id="back-primary-sentence"></div>
</div>

<div class="explain">{{설명}}</div>


<script>
(function(){
  document.querySelectorAll(".title, .word").forEach(function(el){
    for (var i = 0; i < el.childNodes.length; i++) {
      var n = el.childNodes[i];
      if (n.nodeType === 3) {
        n.nodeValue = n.nodeValue.replace(/\s*\/\s*/g, ", ");
      }
    }
  });
  document.querySelectorAll(".pos-raw").forEach(function(el){
    var raw=el.getAttribute("data-pos")||"";
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
    if (!box || !wordEl || !sentEl || !primaryEl) return;

    function cleanHtml(str) {
      if (!str) return "";
      var tmp = document.createElement("div");
      tmp.innerHTML = str;
      var txt = (tmp.textContent || tmp.innerText || "").trim();
      return txt.replace(/[\u2018\u2019]/g, "'").replace(/[\u201C\u201D]/g, '"');
    }

    var rawWord = cleanHtml(wordEl.innerHTML);
    var rawSent = cleanHtml(sentEl.innerHTML);
    if (!rawSent) {
      box.style.display = "none";
      return;
    }

    var sentences = rawSent.split("|||").map(function(s) { 
      var cleaned = s.replace(/<[^>]+>/g, " ").trim();
      cleaned = cleaned.replace(/\([^)]*[\uac00-\ud7a3][^)]*\)/g, "").trim();
      cleaned = cleaned.replace(/^\d+\.\s*/, "").trim();
      return cleaned;
    }).filter(Boolean);

    if (sentences.length === 0) {
      box.style.display = "none";
      return;
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
      "win": "(?:win|wins|winning|won)", "write": "(?:write|writes|writing|wrote|written)",
      "freeze": "(?:freeze|freezes|freezing|froze|frozen)", "throw": "(?:throw|throws|throwing|threw|thrown)",
      "lend": "(?:lend|lends|lending|lent)", "speed": "(?:speed|speeds|speeding|sped)",
      "swear": "(?:swear|swears|swearing|swore|sworn)", "bite": "(?:bite|bites|biting|bit|bitten)",
      "hide": "(?:hide|hides|hiding|hid|hidden)", "wake": "(?:wake|wakes|wakeing|woke|woken)",
      "strike": "(?:strike|strikes|striking|struck)", "be": "(?:be|is|are|was|were|am|been|being)", "is": "(?:be|is|are|was|were|am|been|being)", "are": "(?:be|is|are|was|were|am|been|being)", "was": "(?:be|is|are|was|were|am|been|being)", "were": "(?:be|is|are|was|were|am|been|being)", "am": "(?:be|is|are|was|were|am|been|being)",
      "steal": "(?:steal|steals|stealing|stole|stolen)", "shake": "(?:shake|shakes|shaking|shook|shaken)",
      "blow": "(?:blow|blows|blowing|blew|blown)", "forget": "(?:forget|forgets|forgetting|forgot|forgotten)",
      "forgive": "(?:forgive|forgives|forgiving|forgave|forgiven)", "tear": "(?:tear|tears|tearing|tore|torn)",
      "bear": "(?:bear|bears|bearing|bore|born|borne)", "ride": "(?:ride|rides|riding|rode|ridden)",
      "rise": "(?:rise|rises|rising|rose|risen)", "arise": "(?:arise|arises|arising|arose|arisen)",
      "sink": "(?:sink|sinks|sinking|sank|sunk)", "shrink": "(?:shrink|shrinks|shrinking|shrank|shrunk)",
      "spin": "(?:spin|spins|spinning|spun)", "swing": "(?:swing|swings|swinging|swung)",
      "bind": "(?:bind|binds|binding|bound)", "feed": "(?:feed|feeds|feeding|fed)",
      "flee": "(?:flee|flees|fleeing|fled)", "sweep": "(?:sweep|sweeps|sweeping|swept)",
      "stick": "(?:stick|sticks|sticking|stuck)", "dig": "(?:dig|digs|digging|dug)",
      "bleed": "(?:bleed|bleeds|bleeding|bled)", "breed": "(?:breed|breeds|breeding|bred)",
      "kneel": "(?:kneel|kneels|kneeling|knelt)", "creep": "(?:creep|creeps|creeping|crept)",
      "weep": "(?:weep|weeps|weeping|wept)", "cling": "(?:cling|clings|clinging|clung)",
      "fling": "(?:fling|flings|flinging|flung)", "sting": "(?:sting|stings|stinging|stung)",
      "string": "(?:string|strings|stringing|strung)", "wring": "(?:wring|wrings|wringing|wrung)",
      "spit": "(?:spit|spits|spitting|spat)", "spill": "(?:spill|spills|spilling|spilt|spilled)",
      "leap": "(?:leap|leaps|leaping|leapt|leaped)", "bid": "(?:bid|bids|bidding)",
      "forbid": "(?:forbid|forbids|forbidding|forbade|forbidden)",
      "undergo": "(?:undergo|undergoes|undergoing|underwent|undergone)",
      "undertake": "(?:undertake|undertakes|undertaking|undertook|undertaken)",
      "overcome": "(?:overcome|overcomes|overcoming|overcame)",
      "withdraw": "(?:withdraw|withdraws|withdrawing|withdrew|withdrawn)",
      "withhold": "(?:withhold|withholds|withholding|withheld)",
      "uphold": "(?:uphold|upholds|upholding|upheld)"
    };

    function escapeRegex(s) {
      var specials = ".*+?^${}()|[]/\\-";
      var out = "";
      for (var i = 0; i < s.length; i++) {
        var c = s.charAt(i);
        out += (specials.indexOf(c) !== -1 ? "\\" : "") + c;
      }
      return out;
    }

    function buildTokenPattern(tok) {
      var tLower = tok.toLowerCase();
      if (/^(a|an|the)$/i.test(tLower)) {
        return "(?:a|an|the|this|that|these|those|my|your|his|her|its|our|their|some|any|no)";
      }
      if (IRREGULARS[tLower]) return IRREGULARS[tLower];
      var clean = escapeRegex(tLower);
      if (clean.length > 2 && clean.endsWith("y")) {
        var root = clean.slice(0, -1);
        return root + "(?:y|ies|ied|ying|[a-zA-Z]*)";
      }
      var stem = clean;
      if (stem.length > 3 && (stem.endsWith("e") || stem.endsWith("y"))) {
        stem = stem.slice(0, -1);
      }
      return stem + "[a-zA-Z]*";
    }

    function isPlaceholderToken(t) {
      var c = t.replace(/^[(\[{'\"’]+|[)\]}'\"’]+$/g, "");
      if (/^[ABCXY](?:['’]s)?$/.test(c)) return true;
      if (/^(someone|somebody|sb|something|sth|sb['’]s|sth['’]s|one['’]s|oneself|V|V-ing|v-ing|V-ed|v-ed)$/i.test(c)) return true;
      return false;
    }

    function parseWordChunks(word) {
      var cleanW = (word || "").replace(/<[^>]+>/g, " ").trim();
      var rawTokens = cleanW.split(/[\s/]+/);
      var chunks = [];
      var current = [];
      for (var i = 0; i < rawTokens.length; i++) {
        var tok = rawTokens[i];
        if (isPlaceholderToken(tok)) {
          if (current.length > 0) {
            chunks.push(current);
            current = [];
          }
        } else {
          var cleanTok = tok.replace(/^[^\w]+|[^\w]+$/g, "");
          if (cleanTok) current.push(cleanTok);
        }
      }
      if (current.length > 0) chunks.push(current);
      return chunks;
    }

    function buildChunkPatternPart(chunkTokens) {
      var patternParts = [];
      for (var i = 0; i < chunkTokens.length; i++) {
        if (i > 0) {
          patternParts.push("([,\\x27\\\"]*\\s+(?:[\\w$\\x27\\\",]+\\s+){0,2})");
        }
        patternParts.push("\\b(" + buildTokenPattern(chunkTokens[i]) + ")\\b");
      }
      return patternParts.join("");
    }


    function highlightChunk(m, gIdx, chunkTokens) {
      var out = "";
      var currentSpan = "";
      for (var i = 0; i < chunkTokens.length; i++) {
        if (i > 0) {
          var sep = m[gIdx++];
          if (/^\s+$/.test(sep)) {
            currentSpan += sep;
          } else {
            if (currentSpan) {
              out += '<span class="example-highlight">' + currentSpan + '</span>';
              currentSpan = "";
            }
            out += sep;
          }
        }
        var word = m[gIdx++];
        currentSpan += word;
      }
      if (currentSpan) {
        out += '<span class="example-highlight">' + currentSpan + '</span>';
      }
      return { out: out, gIdx: gIdx };
    }

    function highlightText(text, word) {
      if (!text) return "";
      if (!word) return text;

      var chunks = parseWordChunks(word);
      if (chunks.length === 0) chunks = [word.split(/[\s/]+/)];

      var gapPattern = "(\s+[^.?!;]{0,60}?\s*)";

      try {
        if (chunks.length === 1) {
          var pat = buildChunkPatternPart(chunks[0]);
          var rgx1 = new RegExp(pat, "i");
          var m = rgx1.exec(text);
          if (m) {
            var out = text.slice(0, m.index);
            var res0 = highlightChunk(m, 1, chunks[0]);
            out += res0.out + text.slice(m.index + m[0].length);
            return out;
          }
          for (var tIdx = 0; tIdx < chunks[0].length; tIdx++) {
            var tok = chunks[0][tIdx];
            if (tok.length >= 4 && !/^(a|an|the)$/i.test(tok)) {
              var subRgx = new RegExp("\\b(" + buildTokenPattern(tok) + ")\\b", "i");
              var subM = subRgx.exec(text);
              if (subM) {
                return text.slice(0, subM.index) + '<span class="example-highlight">' + subM[1] + '</span>' + text.slice(subM.index + subM[0].length);
              }
            }
          }
        } else if (chunks.length === 2) {
          var p0 = buildChunkPatternPart(chunks[0]);
          var p1 = buildChunkPatternPart(chunks[1]);
          var rgx2 = new RegExp(p0 + gapPattern + p1, "i");
          var m = rgx2.exec(text);
          if (m) {
            var out = text.slice(0, m.index);
            var res0 = highlightChunk(m, 1, chunks[0]);
            out += res0.out + m[res0.gIdx++];
            var res1 = highlightChunk(m, res0.gIdx, chunks[1]);
            out += res1.out + text.slice(m.index + m[0].length);
            return out;
          }
          var pat0 = buildChunkPatternPart(chunks[0]);
          var rgxFallback = new RegExp(pat0, "i");
          var mFb = rgxFallback.exec(text);
          if (mFb) {
            var out = text.slice(0, mFb.index);
            var resFb = highlightChunk(mFb, 1, chunks[0]);
            out += resFb.out + text.slice(mFb.index + mFb[0].length);
            return out;
          }
        } else if (chunks.length >= 3) {
          var p0 = buildChunkPatternPart(chunks[0]);
          var p1 = buildChunkPatternPart(chunks[1]);
          var p2 = buildChunkPatternPart(chunks[2]);
          var rgx3 = new RegExp(p0 + gapPattern + p1 + gapPattern + p2, "i");
          var m = rgx3.exec(text);
          if (m) {
            var out = text.slice(0, m.index);
            var res0 = highlightChunk(m, 1, chunks[0]);
            out += res0.out + m[res0.gIdx++];
            var res1 = highlightChunk(m, res0.gIdx, chunks[1]);
            out += res1.out + m[res1.gIdx++];
            var res2 = highlightChunk(m, res1.gIdx, chunks[2]);
            out += res2.out + text.slice(m.index + m[0].length);
            return out;
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
  }

  renderBackExample();
  if (typeof onUpdateHook !== "undefined") {
    onUpdateHook.push(renderBackExample);
  }
})();
</script>
<div class="deck">{{Deck}}</div>"""

VOCAB_CARD2_BACK = r"""<script>
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

<!-- 예문 표시 박스 (대표 예문 + 하이라이트) -->
<div class="example" id="back-example-box">
  <span id="back-raw-word" style="display:none;">{{단어}}</span>
  <span id="back-raw-sentence" style="display:none;">{{예문}}</span>
  <div id="back-primary-sentence"></div>
</div>

<div class="explain">{{설명}}</div>


<script>
(function(){
  document.querySelectorAll(".title, .word").forEach(function(el){
    for (var i = 0; i < el.childNodes.length; i++) {
      var n = el.childNodes[i];
      if (n.nodeType === 3) {
        n.nodeValue = n.nodeValue.replace(/\s*\/\s*/g, ", ");
      }
    }
  });
  document.querySelectorAll(".pos-raw").forEach(function(el){
    var raw=el.getAttribute("data-pos")||"";
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
    if (!box || !wordEl || !sentEl || !primaryEl) return;

    function cleanHtml(str) {
      if (!str) return "";
      var tmp = document.createElement("div");
      tmp.innerHTML = str;
      var txt = (tmp.textContent || tmp.innerText || "").trim();
      return txt.replace(/[\u2018\u2019]/g, "'").replace(/[\u201C\u201D]/g, '"');
    }

    var rawWord = cleanHtml(wordEl.innerHTML);
    var rawSent = cleanHtml(sentEl.innerHTML);
    if (!rawSent) {
      box.style.display = "none";
      return;
    }

    var sentences = rawSent.split("|||").map(function(s) { 
      var cleaned = s.replace(/<[^>]+>/g, " ").trim();
      cleaned = cleaned.replace(/\([^)]*[\uac00-\ud7a3][^)]*\)/g, "").trim();
      cleaned = cleaned.replace(/^\d+\.\s*/, "").trim();
      return cleaned;
    }).filter(Boolean);

    if (sentences.length === 0) {
      box.style.display = "none";
      return;
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
      "win": "(?:win|wins|winning|won)", "write": "(?:write|writes|writing|wrote|written)",
      "freeze": "(?:freeze|freezes|freezing|froze|frozen)", "throw": "(?:throw|throws|throwing|threw|thrown)",
      "lend": "(?:lend|lends|lending|lent)", "speed": "(?:speed|speeds|speeding|sped)",
      "swear": "(?:swear|swears|swearing|swore|sworn)", "bite": "(?:bite|bites|biting|bit|bitten)",
      "hide": "(?:hide|hides|hiding|hid|hidden)", "wake": "(?:wake|wakes|wakeing|woke|woken)",
      "strike": "(?:strike|strikes|striking|struck)", "be": "(?:be|is|are|was|were|am|been|being)", "is": "(?:be|is|are|was|were|am|been|being)", "are": "(?:be|is|are|was|were|am|been|being)", "was": "(?:be|is|are|was|were|am|been|being)", "were": "(?:be|is|are|was|were|am|been|being)", "am": "(?:be|is|are|was|were|am|been|being)",
      "steal": "(?:steal|steals|stealing|stole|stolen)", "shake": "(?:shake|shakes|shaking|shook|shaken)",
      "blow": "(?:blow|blows|blowing|blew|blown)", "forget": "(?:forget|forgets|forgetting|forgot|forgotten)",
      "forgive": "(?:forgive|forgives|forgiving|forgave|forgiven)", "tear": "(?:tear|tears|tearing|tore|torn)",
      "bear": "(?:bear|bears|bearing|bore|born|borne)", "ride": "(?:ride|rides|riding|rode|ridden)",
      "rise": "(?:rise|rises|rising|rose|risen)", "arise": "(?:arise|arises|arising|arose|arisen)",
      "sink": "(?:sink|sinks|sinking|sank|sunk)", "shrink": "(?:shrink|shrinks|shrinking|shrank|shrunk)",
      "spin": "(?:spin|spins|spinning|spun)", "swing": "(?:swing|swings|swinging|swung)",
      "bind": "(?:bind|binds|binding|bound)", "feed": "(?:feed|feeds|feeding|fed)",
      "flee": "(?:flee|flees|fleeing|fled)", "sweep": "(?:sweep|sweeps|sweeping|swept)",
      "stick": "(?:stick|sticks|sticking|stuck)", "dig": "(?:dig|digs|digging|dug)",
      "bleed": "(?:bleed|bleeds|bleeding|bled)", "breed": "(?:breed|breeds|breeding|bred)",
      "kneel": "(?:kneel|kneels|kneeling|knelt)", "creep": "(?:creep|creeps|creeping|crept)",
      "weep": "(?:weep|weeps|weeping|wept)", "cling": "(?:cling|clings|clinging|clung)",
      "fling": "(?:fling|flings|flinging|flung)", "sting": "(?:sting|stings|stinging|stung)",
      "string": "(?:string|strings|stringing|strung)", "wring": "(?:wring|wrings|wringing|wrung)",
      "spit": "(?:spit|spits|spitting|spat)", "spill": "(?:spill|spills|spilling|spilt|spilled)",
      "leap": "(?:leap|leaps|leaping|leapt|leaped)", "bid": "(?:bid|bids|bidding)",
      "forbid": "(?:forbid|forbids|forbidding|forbade|forbidden)",
      "undergo": "(?:undergo|undergoes|undergoing|underwent|undergone)",
      "undertake": "(?:undertake|undertakes|undertaking|undertook|undertaken)",
      "overcome": "(?:overcome|overcomes|overcoming|overcame)",
      "withdraw": "(?:withdraw|withdraws|withdrawing|withdrew|withdrawn)",
      "withhold": "(?:withhold|withholds|withholding|withheld)",
      "uphold": "(?:uphold|upholds|upholding|upheld)"
    };

    function escapeRegex(s) {
      var specials = ".*+?^${}()|[]/\\-";
      var out = "";
      for (var i = 0; i < s.length; i++) {
        var c = s.charAt(i);
        out += (specials.indexOf(c) !== -1 ? "\\" : "") + c;
      }
      return out;
    }

    function buildTokenPattern(tok) {
      var tLower = tok.toLowerCase();
      if (/^(a|an|the)$/i.test(tLower)) {
        return "(?:a|an|the|this|that|these|those|my|your|his|her|its|our|their|some|any|no)";
      }
      if (IRREGULARS[tLower]) return IRREGULARS[tLower];
      var clean = escapeRegex(tLower);
      if (clean.length > 2 && clean.endsWith("y")) {
        var root = clean.slice(0, -1);
        return root + "(?:y|ies|ied|ying|[a-zA-Z]*)";
      }
      var stem = clean;
      if (stem.length > 3 && (stem.endsWith("e") || stem.endsWith("y"))) {
        stem = stem.slice(0, -1);
      }
      return stem + "[a-zA-Z]*";
    }

    function isPlaceholderToken(t) {
      var c = t.replace(/^[(\[{'\"’]+|[)\]}'\"’]+$/g, "");
      if (/^[ABCXY](?:['’]s)?$/.test(c)) return true;
      if (/^(someone|somebody|sb|something|sth|sb['’]s|sth['’]s|one['’]s|oneself|V|V-ing|v-ing|V-ed|v-ed)$/i.test(c)) return true;
      return false;
    }

    function parseWordChunks(word) {
      var cleanW = (word || "").replace(/<[^>]+>/g, " ").trim();
      var rawTokens = cleanW.split(/[\s/]+/);
      var chunks = [];
      var current = [];
      for (var i = 0; i < rawTokens.length; i++) {
        var tok = rawTokens[i];
        if (isPlaceholderToken(tok)) {
          if (current.length > 0) {
            chunks.push(current);
            current = [];
          }
        } else {
          var cleanTok = tok.replace(/^[^\w]+|[^\w]+$/g, "");
          if (cleanTok) current.push(cleanTok);
        }
      }
      if (current.length > 0) chunks.push(current);
      return chunks;
    }

    function buildChunkPatternPart(chunkTokens) {
      var patternParts = [];
      for (var i = 0; i < chunkTokens.length; i++) {
        if (i > 0) {
          patternParts.push("([,\\x27\\\"]*\\s+(?:[\\w$\\x27\\\",]+\\s+){0,2})");
        }
        patternParts.push("\\b(" + buildTokenPattern(chunkTokens[i]) + ")\\b");
      }
      return patternParts.join("");
    }


    function highlightChunk(m, gIdx, chunkTokens) {
      var out = "";
      var currentSpan = "";
      for (var i = 0; i < chunkTokens.length; i++) {
        if (i > 0) {
          var sep = m[gIdx++];
          if (/^\s+$/.test(sep)) {
            currentSpan += sep;
          } else {
            if (currentSpan) {
              out += '<span class="example-highlight">' + currentSpan + '</span>';
              currentSpan = "";
            }
            out += sep;
          }
        }
        var word = m[gIdx++];
        currentSpan += word;
      }
      if (currentSpan) {
        out += '<span class="example-highlight">' + currentSpan + '</span>';
      }
      return { out: out, gIdx: gIdx };
    }

    function highlightText(text, word) {
      if (!text) return "";
      if (!word) return text;

      var chunks = parseWordChunks(word);
      if (chunks.length === 0) chunks = [word.split(/[\s/]+/)];

      var gapPattern = "(\s+[^.?!;]{0,60}?\s*)";

      try {
        if (chunks.length === 1) {
          var pat = buildChunkPatternPart(chunks[0]);
          var rgx1 = new RegExp(pat, "i");
          var m = rgx1.exec(text);
          if (m) {
            var out = text.slice(0, m.index);
            var res0 = highlightChunk(m, 1, chunks[0]);
            out += res0.out + text.slice(m.index + m[0].length);
            return out;
          }
          for (var tIdx = 0; tIdx < chunks[0].length; tIdx++) {
            var tok = chunks[0][tIdx];
            if (tok.length >= 4 && !/^(a|an|the)$/i.test(tok)) {
              var subRgx = new RegExp("\\b(" + buildTokenPattern(tok) + ")\\b", "i");
              var subM = subRgx.exec(text);
              if (subM) {
                return text.slice(0, subM.index) + '<span class="example-highlight">' + subM[1] + '</span>' + text.slice(subM.index + subM[0].length);
              }
            }
          }
        } else if (chunks.length === 2) {
          var p0 = buildChunkPatternPart(chunks[0]);
          var p1 = buildChunkPatternPart(chunks[1]);
          var rgx2 = new RegExp(p0 + gapPattern + p1, "i");
          var m = rgx2.exec(text);
          if (m) {
            var out = text.slice(0, m.index);
            var res0 = highlightChunk(m, 1, chunks[0]);
            out += res0.out + m[res0.gIdx++];
            var res1 = highlightChunk(m, res0.gIdx, chunks[1]);
            out += res1.out + text.slice(m.index + m[0].length);
            return out;
          }
          var pat0 = buildChunkPatternPart(chunks[0]);
          var rgxFallback = new RegExp(pat0, "i");
          var mFb = rgxFallback.exec(text);
          if (mFb) {
            var out = text.slice(0, mFb.index);
            var resFb = highlightChunk(mFb, 1, chunks[0]);
            out += resFb.out + text.slice(mFb.index + mFb[0].length);
            return out;
          }
        } else if (chunks.length >= 3) {
          var p0 = buildChunkPatternPart(chunks[0]);
          var p1 = buildChunkPatternPart(chunks[1]);
          var p2 = buildChunkPatternPart(chunks[2]);
          var rgx3 = new RegExp(p0 + gapPattern + p1 + gapPattern + p2, "i");
          var m = rgx3.exec(text);
          if (m) {
            var out = text.slice(0, m.index);
            var res0 = highlightChunk(m, 1, chunks[0]);
            out += res0.out + m[res0.gIdx++];
            var res1 = highlightChunk(m, res0.gIdx, chunks[1]);
            out += res1.out + m[res1.gIdx++];
            var res2 = highlightChunk(m, res1.gIdx, chunks[2]);
            out += res2.out + text.slice(m.index + m[0].length);
            return out;
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
  }

  renderBackExample();
  if (typeof onUpdateHook !== "undefined") {
    onUpdateHook.push(renderBackExample);
  }
})();
</script>
<div class="deck">{{Deck}}</div>"""


def apply_vocab_updates():
    from integrations.anki_connect import AnkiConnector
    from config import MODEL_VOCAB

    print("[*] Verifying JS Syntax in updated Vocabulary templates...")
    templates = {
        "Card 1 Front": VOCAB_CARD1_FRONT,
        "Card 1 Back": VOCAB_CARD1_BACK,
        "Card 2 Back": VOCAB_CARD2_BACK,
    }
    for name, html in templates.items():
        scripts = [part.split("</script>")[0] for part in html.split("<script>") if "</script>" in part]
        for idx, sc in enumerate(scripts):
            tfile = f"/tmp/verify_chunk_vocab_{name.replace(' ', '_')}_{idx}.js"
            with open(tfile, "w") as f:
                f.write(sc)
            res = subprocess.run(["node", "--check", tfile], capture_output=True, text=True)
            if res.returncode != 0:
                print(f"[!] Syntax error in {name} #{idx}: {res.stderr}")
                raise RuntimeError("JS syntax check failed")
            print(f"  ✓ {name} #{idx}: Syntax OK")

    print("\n[*] Updating Anki Model Templates for English Vocabulary...")
    model_tpls = AnkiConnector.invoke("modelTemplates", modelName=MODEL_VOCAB)
    model_tpls["카드 1"]["Front"] = VOCAB_CARD1_FRONT
    model_tpls["카드 1"]["Back"] = VOCAB_CARD1_BACK
    model_tpls["카드 2"]["Back"] = VOCAB_CARD2_BACK
    AnkiConnector.update_model_templates(MODEL_VOCAB, model_tpls)
    print("  ✓ English Vocabulary templates updated in Anki.")

    config_file = BASE_DIR / "data" / "design_config.json"
    if config_file.exists():
        with open(config_file, "r", encoding="utf-8") as f:
            design = json.load(f)
        if MODEL_VOCAB in design:
            design[MODEL_VOCAB]["templates"] = model_tpls
            with open(config_file, "w", encoding="utf-8") as f:
                json.dump(design, f, ensure_ascii=False, indent=2)
            print("  ✓ data/design_config.json updated successfully.")

if __name__ == "__main__":
    apply_vocab_updates()
