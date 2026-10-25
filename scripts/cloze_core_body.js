
/* ===== Cloze core: single matcher shared by front (cloze) and back (highlight) =====
 * Rules:
 *  - content words, prepositions, adverbs: blank (front) / underline (back)
 *  - articles: exposed in front, underlined in back (part of the expression)
 *  - slots (A, A's, sb, sth, one's, V-ing): exposed in front; underlined only when
 *    they sit BETWEEN fixed words; leading/trailing slots are never part of the match
 *  - first non-stopword fixed token gets a first-letter hint
 *  - no partial matching: either the whole expression matches or the sentence is shown as-is
 */
var CLOZE_STOP = /^(in|on|at|to|for|of|by|with|from|up|out|off|over|about|as|into|onto|upon|through|under|down|away|back|be|is|are|was|were|am|been|being|it|its|one)$/i;

function clozeNormalize(str) {
  if (!str) return "";
  var s = String(str).replace(/<[^>]*>/g, " ");
  s = s.replace(/&nbsp;/g, " ").replace(/&lt;/g, "<").replace(/&gt;/g, ">")
       .replace(/&quot;/g, '"').replace(/&#x27;|&#39;/g, "'").replace(/&amp;/g, "&");
  s = s.replace(/[\u2018\u2019]/g, "'").replace(/[\u201C\u201D]/g, '"');
  return s.replace(/\s+/g, " ").trim();
}

function clozeSplitSentences(raw) {
  var txt = String(raw || "").replace(/<br\s*\/?>/gi, " ");
  return txt.split("|||").map(function (s) {
    var c = clozeNormalize(s);
    c = c.replace(/\([^)]*[\uac00-\ud7a3][^)]*\)/g, "").trim();
    c = c.replace(/^\d+\.\s*/, "").trim();
    return c;
  }).filter(Boolean);
}

function clozeIsSlot(t) {
  var c = t.replace(/^[(\[{'"]+|[)\]}'",.;:!?]+$/g, "");
  if (/^[ABCXY](?:'s)?$/.test(c)) return true;
  if (/^(someone|somebody|sb|something|sth|someone's|sb's|sth's|one's|oneself|V|V-ing|V-ed)$/i.test(c)) return true;
  return false;
}

function clozeParse(word) {
  var w = clozeNormalize(word).replace(/\s*\([^)]*\)/g, " ").trim();
  var raw = w.split(/\s+/).filter(Boolean);
  var toks = [];
  for (var i = 0; i < raw.length; i++) {
    var t = raw[i];
    if (clozeIsSlot(t)) {
      if (toks.length && toks[toks.length - 1].slot) continue;
      toks.push({ slot: true });
    } else {
      var clean = t.replace(/^[^\w]+|[^\w]+$/g, "");
      if (clean) toks.push({ slot: false, text: clean });
    }
  }
  while (toks.length && toks[0].slot) toks.shift();
  while (toks.length && toks[toks.length - 1].slot) toks.pop();
  return toks;
}

function clozeEscape(s) {
  return s.replace(/[.*+?^$(){}|\[\]\\\/-]/g, "\\$&");
}

function clozeOnePattern(t) {
  var lower = t.toLowerCase();
  if (clozeIsArticle(lower)) return "(?:a|an|the|this|that|these|those|my|your|his|her|its|our|their|some|any)";
  if (/^(be|is|are|was|were|am|been|being)$/.test(lower)) return "(?:be|is|are|was|were|am|been|being|'m|'s|'re)";
  if (CLOZE_IRREGULARS[lower]) return CLOZE_IRREGULARS[lower];
  var esc = clozeEscape(lower);
  if (lower === "be") return "(?:be|is|are|was|were|am|been|being|'m|'s|'re)";
  if (lower.length <= 2 || CLOZE_STOP.test(lower) || clozeIsArticle(lower)) return esc;
  if (/[^aeiou]y$/.test(lower)) {
    return clozeEscape(lower.slice(0, -1)) + "(?:y|ies|ied|ying|ier|iest|ily|iness)";
  }
  if (/e$/.test(lower)) {
    return clozeEscape(lower.slice(0, -1)) + "(?:e|es|ed|er|ers|ing|ely|y)";
  }
  return esc + "(?:s|es|ed|ing|er|ers|ly|[bdgmnprt](?:ed|ing|er))?";
}

function clozeTokenPattern(text) {
  return "(?:" + text.split("/").map(clozeOnePattern).join("|") + ")";
}

var CLOZE_CACHE = {};

function clozeBuild(word) {
  if (CLOZE_CACHE[word]) return CLOZE_CACHE[word];
  var toks = clozeParse(word);
  var re = "";
  var meta = [];
  var pendingSlot = false;
  for (var i = 0; i < toks.length; i++) {
    var t = toks[i];
    if (t.slot) { pendingSlot = true; continue; }
    if (meta.length > 0) {
      re += pendingSlot ? "([,;]?\\s+(?:[^\\s.?!;]+\\s+){1,6}?)" : "([,;]?\\s+|-)";
    }
    re += "(?:\\b|(?=')|(?<=')|(?<=\\w))(" + clozeTokenPattern(t.text) + ")\\b";
    meta.push(t);
    pendingSlot = false;
  }
  var built = meta.length ? { rgx: new RegExp(re, "i"), meta: meta } : null;
  CLOZE_CACHE[word] = built;
  return built;
}

function clozeMatch(sentence, word) {
  var b = clozeBuild(word);
  if (!b) return null;
  var m = b.rgx.exec(sentence);
  if (!m) return null;
  return { m: m, meta: b.meta };
}

function clozeIsArticle(text) {
  return /^(a|an|the)$/i.test(text);
}

function clozeMaskWord(w, hint) {
  var out = "";
  for (var i = 0; i < w.length; i++) {
    var ch = w.charAt(i);
    if (/[A-Za-z0-9]/.test(ch)) {
      out += (hint && i === 0 && w.length > 1) ? ch : "_";
    } else {
      out += ch;
    }
  }
  return '<span class="cloze-blank">' + out + "</span>";
}

function clozeMask(sentence, word) {
  var r = clozeMatch(sentence, word);
  if (!r) return null;
  var m = r.m, meta = r.meta;
  var hintIdx = -1, firstNonArt = -1;
  for (var i = 0; i < meta.length; i++) {
    if (clozeIsArticle(meta[i].text)) continue;
    if (firstNonArt < 0) firstNonArt = i;
    if (!CLOZE_STOP.test(meta[i].text)) { hintIdx = i; break; }
  }
  if (hintIdx < 0) hintIdx = firstNonArt;
  var out = sentence.slice(0, m.index);
  for (var j = 0; j < meta.length; j++) {
    if (j > 0) out += m[2 * j];
    var w = m[1 + 2 * j];
    out += clozeIsArticle(meta[j].text) ? w : clozeMaskWord(w, j === hintIdx);
  }
  return out + sentence.slice(m.index + m[0].length);
}

function clozeHighlight(sentence, word) {
  var r = clozeMatch(sentence, word);
  if (!r) return null;
  var m = r.m;
  return sentence.slice(0, m.index) + '<span class="example-highlight">' + m[0] + "</span>" +
         sentence.slice(m.index + m[0].length);
}

function clozeFront(sentences, word) {
  var start = sentences.length > 1 ? Math.floor(Math.random() * sentences.length) : 0;
  for (var k = 0; k < sentences.length; k++) {
    var idx = (start + k) % sentences.length;
    var html = clozeMask(sentences[idx], word);
    if (html) return { sentence: sentences[idx], html: html };
  }
  return { sentence: sentences[start], html: null };
}

function clozeBack(sentences, word, saved) {
  var order = [];
  if (saved && sentences.indexOf(saved) !== -1) order.push(saved);
  for (var i = 0; i < sentences.length; i++) {
    if (order.indexOf(sentences[i]) === -1) order.push(sentences[i]);
  }
  for (var k = 0; k < order.length; k++) {
    var html = clozeHighlight(order[k], word);
    if (html) return { sentence: order[k], html: html };
  }
  return { sentence: order[0], html: null };
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = {
    clozeNormalize: clozeNormalize, clozeSplitSentences: clozeSplitSentences,
    clozeParse: clozeParse, clozeMatch: clozeMatch, clozeMask: clozeMask,
    clozeHighlight: clozeHighlight, clozeFront: clozeFront, clozeBack: clozeBack
  };
}
