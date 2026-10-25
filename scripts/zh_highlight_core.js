// Chinese Sentence card back: mark the linked words returned by /api/links/badge/sentence?lang=zh.
// Inlined into the template by core/card_templates.py; tested by scripts/test_zh_highlight.js.
// The server already decided which words are linked (jieba); here we only find where they sit.
function zhEscape(s) {
  return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

function zhHighlight(text, items) {
  if (!text || !items || items.length === 0) return null;
  var sorted = items.slice().sort(function(a, b) { return b.word.length - a.word.length; });
  var ranges = [];
  sorted.forEach(function(item) {
    var w = item.word;
    if (!w) return;
    var from = 0, at;
    while ((at = text.indexOf(w, from)) !== -1) {
      var end = at + w.length;
      var overlap = ranges.some(function(r) { return Math.max(at, r.start) < Math.min(end, r.end); });
      if (!overlap) ranges.push({ start: at, end: end, item: item });
      from = at + 1;
    }
  });
  if (ranges.length === 0) return null;
  ranges.sort(function(a, b) { return a.start - b.start; });
  var out = "", last = 0;
  ranges.forEach(function(r) {
    var label = r.item.word;
    if (r.item.pos) label += " (" + r.item.pos + ")";
    if (r.item.meaning) label += ": " + r.item.meaning;
    var safe = zhEscape(label);
    out += zhEscape(text.slice(last, r.start)) +
      '<span class="linked-word" data-tooltip="' + safe + '" title="' + safe + '">' + zhEscape(text.slice(r.start, r.end)) + "</span>";
    last = r.end;
  });
  return out + zhEscape(text.slice(last));
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = { zhHighlight: zhHighlight, zhEscape: zhEscape };
}
