var CLOZE_IRREGULAR_GROUPS = [
  "be is are was were am been being", "get gets getting got gotten", "take takes taking took taken",
  "make makes making made", "give gives giving gave given", "come comes coming came",
  "go goes going went gone", "see sees seeing saw seen", "have has having had",
  "run runs running ran", "keep keeps keeping kept", "find finds finding found",
  "fall falls falling fell fallen", "break breaks breaking broke broken",
  "bring brings bringing brought", "buy buys buying bought", "catch catches catching caught",
  "choose chooses choosing chose chosen", "do does doing did done", "draw draws drawing drew drawn",
  "drive drives driving drove driven", "feel feels feeling felt", "fly flies flying flew flown",
  "grow grows growing grew grown", "hear hears hearing heard", "hold holds holding held",
  "know knows knowing knew known", "leave leaves leaving left", "lose loses losing lost",
  "pay pays paying paid", "put puts putting", "read reads reading", "say says saying said",
  "send sends sending sent", "show shows showing showed shown", "speak speaks speaking spoke spoken",
  "spend spends spending spent", "stand stands standing stood", "tell tells telling told",
  "think thinks thinking thought", "wear wears wearing wore worn", "win wins winning won",
  "write writes writing wrote written", "freeze freezes freezing froze frozen",
  "throw throws throwing threw thrown", "lend lends lending lent", "speed speeds speeding sped",
  "swear swears swearing swore sworn", "bite bites biting bit bitten", "hide hides hiding hid hidden",
  "wake wakes waking woke woken", "strike strikes striking struck", "steal steals stealing stole stolen",
  "shake shakes shaking shook shaken", "blow blows blowing blew blown",
  "forget forgets forgetting forgot forgotten", "forgive forgives forgiving forgave forgiven",
  "tear tears tearing tore torn", "bear bears bearing bore born borne", "ride rides riding rode ridden",
  "rise rises rising rose risen", "arise arises arising arose arisen", "sink sinks sinking sank sunk",
  "shrink shrinks shrinking shrank shrunk", "spin spins spinning spun", "swing swings swinging swung",
  "bind binds binding bound", "feed feeds feeding fed", "flee flees fleeing fled",
  "sweep sweeps sweeping swept", "stick sticks sticking stuck", "dig digs digging dug",
  "bleed bleeds bleeding bled", "breed breeds breeding bred", "kneel kneels kneeling knelt",
  "creep creeps creeping crept", "weep weeps weeping wept", "cling clings clinging clung",
  "fling flings flinging flung", "sting stings stinging stung", "string strings stringing strung",
  "wring wrings wringing wrung", "spit spits spitting spat", "spill spills spilling spilt spilled",
  "leap leaps leaping leapt leaped", "bid bids bidding", "forbid forbids forbidding forbade forbidden",
  "undergo undergoes undergoing underwent undergone", "undertake undertakes undertaking undertook undertaken",
  "overcome overcomes overcoming overcame", "withdraw withdraws withdrawing withdrew withdrawn",
  "withhold withholds withholding withheld", "uphold upholds upholding upheld",
  "lay lays laying laid", "lie lies lying lay lain lied", "set sets setting", "cut cuts cutting",
  "let lets letting", "hit hits hitting", "sit sits sitting sat", "meet meets meeting met",
  "lead leads leading led", "build builds building built", "begin begins beginning began begun",
  "seek seeks seeking sought", "sell sells selling sold", "teach teaches teaching taught",
  "become becomes becoming became", "mean means meaning meant", "hang hangs hanging hung",
  "shoot shoots shooting shot", "shut shuts shutting", "sing sings singing sang sung",
  "swim swims swimming swam swum", "drink drinks drinking drank drunk", "eat eats eating ate eaten",
  "lend lends lending lent", "rid rids ridding", "slide slides sliding slid", "split splits splitting",
  "spread spreads spreading", "thrust thrusts thrusting", "burst bursts bursting", "cast casts casting",
  "cost costs costing", "deal deals dealing dealt", "dream dreams dreaming dreamt dreamed",
  "light lights lighting lit lighted", "mistake mistakes mistaking mistook mistaken",
  "overtake overtakes overtaking overtook overtaken", "prove proves proving proved proven",
  "quit quits quitting", "shed sheds shedding", "slay slays slaying slew slain", "sow sows sowing sowed sown",
  "stride strides striding strode stridden", "sweat sweats sweating", "tread treads treading trod trodden",
  "understand understands understanding understood", "wind winds winding wound",
  "fight fights fighting fought", "swell swells swelling swelled swollen",
  "oversleep oversleeps oversleeping overslept", "sleep sleeps sleeping slept"
];
var CLOZE_IRREGULARS = {};
CLOZE_IRREGULAR_GROUPS.forEach(function (g) {
  var forms = g.split(" ");
  var pat = "(?:" + forms.join("|") + ")";
  forms.forEach(function (f) {
    if (!CLOZE_IRREGULARS[f]) CLOZE_IRREGULARS[f] = pat;
  });
});

/* ===== Cloze core: single matcher shared by front (cloze) and back (highlight) =====
 * Rules:
 *  - content words, prepositions, adverbs: blank (front) / underline (back)
 *  - articles: exposed in front, underlined in back (part of the expression)
 *  - slots (A, A's, sb, sth, one's, V-ing): exposed in front; underlined only when
 *    they sit BETWEEN fixed words; leading/trailing slots are never part of the match
 *  - first non-stopword fixed token gets a first-letter hint
 *  - strict match first; only if it fails, a loose match allows up to 2 extra words (no commas)
 *    or "a lot of" between
 *    fixed words ("made a good point"), an empty middle slot ("putting off the meeting"),
 *    a missing article ("cracking jokes") and a missing leading be ("felt pressured to")
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

function clozeOnePattern(t, loose) {
  var lower = t.toLowerCase();
  if (clozeIsArticle(lower)) return "(?:a|an|the|this|that|these|those|my|your|his|her|its|our|their|some|any)";
  if (/^(be|is|are|was|were|am|been|being)$/.test(lower)) return "(?:be|is|are|was|were|am|been|being|'m|'s|'re)";
  // contractions only in the strict (adjacent) match: "I've been meaning to"
  if (lower === "have") return loose ? "(?:have|has|having|had)" : "(?:have|has|having|had|'ve|'d)";
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

function clozeTokenPattern(text, loose) {
  return "(?:" + text.split("/").map(function (t) { return clozeOnePattern(t, loose); }).join("|") + ")";
}

var CLOZE_CACHE = {};

function clozeRegex(toks, loose) {
  // One separator group and one token group per fixed word, so match groups line up with
  // meta: m[1 + 2j] is word j and m[2j] the text before it (undefined when optional and absent).
  var seps = [], words = [];
  var pendingSlot = false;
  for (var i = 0; i < toks.length; i++) {
    var t = toks[i];
    if (t.slot) { pendingSlot = true; continue; }
    if (words.length > 0) {
      if (pendingSlot) {
        // loose: the slot may be empty ("putting off the meeting", "bear in mind that")
        seps.push(loose ? "([,;]?\\s+(?:[^\\s.?!;]+\\s+){0,8}?)" : "([,;]?\\s+(?:[^\\s.?!;]+\\s+){1,6}?)");
      } else {
        // loose: up to 2 extra words without commas ("made a good point"), or "a lot of"
        seps.push(loose ? "([,;]?\\s+(?:a\\s+lot\\s+of\\s+|(?:[^\\s.?!;,]+\\s+){0,2}?)|-)" : "([,;]?\\s+|-)");
      }
    } else {
      seps.push("");
    }
    // loose: never start inside a word ("software" must not yield "are")
    var start = loose ? "(?:\\b|(?='))" : "(?:\\b|(?=')|(?<=')|(?<=\\w))";
    words.push({ text: t.text, re: start + "(" + clozeTokenPattern(t.text, loose) + ")\\b" });
    pendingSlot = false;
  }
  var re = "";
  var k = 0;
  if (loose && words.length > 1 && /^(be|is|are|was|were|am)$/i.test(words[0].text)) {
    // "be pressured to V" ~ "felt pressured to": be and the gap after it are optional together
    re = "(?:" + words[0].re + seps[1] + ")?" + words[1].re;
    k = 2;
  }
  for (; k < words.length; k++) {
    if (loose && k > 0 && clozeIsArticle(words[k].text)) {
      re += "(?:" + seps[k] + words[k].re + ")?";   // "crack a joke" ~ "cracking jokes"
    } else {
      re += seps[k] + words[k].re;
    }
  }
  return new RegExp(re, "i");
}

function clozeBuild(word) {
  if (CLOZE_CACHE[word]) return CLOZE_CACHE[word];
  var toks = clozeParse(word);
  var meta = toks.filter(function (t) { return !t.slot; });
  // Strict first; the loose pattern is only a fallback, so strict matches never change.
  var built = meta.length ? { rgx: clozeRegex(toks, false), loose: clozeRegex(toks, true), meta: meta } : null;
  CLOZE_CACHE[word] = built;
  return built;
}

// mode: "strict", "loose" or undefined (strict, then loose)
function clozeMatch(sentence, word, mode) {
  var b = clozeBuild(word);
  if (!b) return null;
  var m = mode === "loose" ? b.loose.exec(sentence)
        : mode === "strict" ? b.rgx.exec(sentence)
        : (b.rgx.exec(sentence) || b.loose.exec(sentence));
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

function clozeMask(sentence, word, mode) {
  var r = clozeMatch(sentence, word, mode);
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
    if (j > 0 && m[2 * j] !== undefined) out += m[2 * j];
    var w = m[1 + 2 * j];
    if (w === undefined) continue;   // optional word absent in the loose match
    out += clozeIsArticle(meta[j].text) ? w : clozeMaskWord(w, j === hintIdx);
  }
  return out + sentence.slice(m.index + m[0].length);
}

function clozeHighlight(sentence, word, mode) {
  var r = clozeMatch(sentence, word, mode);
  if (!r) return null;
  var m = r.m;
  var lead = m[0].match(/^\s*/)[0];  // a loose match may start at the space before the first word
  return sentence.slice(0, m.index) + lead + '<span class="example-highlight">' + m[0].slice(lead.length) + "</span>" +
         sentence.slice(m.index + m[0].length);
}

// A note uses the loose match only when none of its examples matches strictly, so notes that
// already work are unaffected and unrelated extra examples are never force-matched.
function clozeNoteMode(sentences, word) {
  for (var i = 0; i < sentences.length; i++) {
    if (clozeMatch(sentences[i], word, "strict")) return "strict";
  }
  return "loose";
}

function clozeFront(sentences, word) {
  var mode = clozeNoteMode(sentences, word);
  var start = sentences.length > 1 ? Math.floor(Math.random() * sentences.length) : 0;
  for (var k = 0; k < sentences.length; k++) {
    var idx = (start + k) % sentences.length;
    var html = clozeMask(sentences[idx], word, mode);
    if (html) return { sentence: sentences[idx], html: html };
  }
  return { sentence: sentences[start], html: null };
}

function clozeBack(sentences, word, saved) {
  var mode = clozeNoteMode(sentences, word);
  var order = [];
  if (saved && sentences.indexOf(saved) !== -1) order.push(saved);
  for (var i = 0; i < sentences.length; i++) {
    if (order.indexOf(sentences[i]) === -1) order.push(sentences[i]);
  }
  for (var k = 0; k < order.length; k++) {
    var html = clozeHighlight(order[k], word, mode);
    if (html) return { sentence: order[k], html: html };
  }
  return { sentence: order[0], html: null };
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = {
    clozeNormalize: clozeNormalize, clozeSplitSentences: clozeSplitSentences,
    clozeParse: clozeParse, clozeMatch: clozeMatch, clozeMask: clozeMask,
    clozeHighlight: clozeHighlight, clozeFront: clozeFront, clozeBack: clozeBack,
    clozeNoteMode: clozeNoteMode
  };
}
