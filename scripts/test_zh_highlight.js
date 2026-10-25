// Cases for scripts/zh_highlight_core.js (Chinese Sentence card back). Run: node scripts/test_zh_highlight.js
// Pure JS, no Anki access.
const assert = require("assert");
const z = require("./zh_highlight_core.js");

const HAO = { word: "好", meaning: "좋다, 안녕하다", pos: "adj, v" };
const DAJIA = { word: "大家", meaning: "여러분, 모두", pos: "pron" };
const HAOCHI = { word: "好吃", meaning: "맛있다", pos: "adj" };

// Each linked word is wrapped once, with word (pos): meaning as the tooltip.
assert.strictEqual(
  z.zhHighlight("大家好！", [HAO, DAJIA]),
  '<span class="linked-word" data-tooltip="大家 (pron): 여러분, 모두" title="大家 (pron): 여러분, 모두">大家</span>' +
  '<span class="linked-word" data-tooltip="好 (adj, v): 좋다, 안녕하다" title="好 (adj, v): 좋다, 안녕하다">好</span>！'
);

// Longest word wins; a shorter word inside it is not highlighted again.
const out = z.zhHighlight("可以推荐好吃的饭店吗?", [HAO, HAOCHI]);
assert.strictEqual((out.match(/class="linked-word"/g) || []).length, 1, out);
assert.ok(out.includes(">好吃</span>"), out);

// Every occurrence is marked.
assert.strictEqual((z.zhHighlight("好，好。", [HAO]).match(/>好<\/span>/g) || []).length, 2);

// Nothing linked or no match -> null (template leaves the sentence untouched).
assert.strictEqual(z.zhHighlight("大家好！", []), null);
assert.strictEqual(z.zhHighlight("你们", [DAJIA]), null);

// Sentence text and labels are escaped (textContent can contain < and quotes).
const esc = z.zhHighlight('<b>大家</b>"', [{ word: "大家", meaning: 'say "hi"', pos: "" }]);
assert.ok(esc.startsWith("&lt;b&gt;<span"), esc);
assert.ok(esc.includes('data-tooltip="大家: say &quot;hi&quot;"'), esc);
assert.ok(esc.endsWith("&lt;/b&gt;&quot;"), esc);

console.log("zh_highlight: all cases passed");
