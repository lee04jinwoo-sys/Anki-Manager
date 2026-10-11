// Regression cases for scripts/cloze_core.js. Run: node scripts/test_cloze_cases.js
// Pure JS, no Anki access.
const assert = require("assert");
const c = require("./cloze_core.js");

// Slot in the middle of the expression (the old template's gap regex lost its \s escape,
// so only the first word was blanked/highlighted).
const w1 = "figure A out from the context clue";
const s1 = "Even though the word was new, I could figure its meaning out from the context clue.";
assert.strictEqual(
  c.clozeHighlight(s1, w1),
  'Even though the word was new, I could <span class="example-highlight">figure its meaning out from the context clue</span>.'
);
const front1 = c.clozeMask(s1, w1);
assert.ok(front1.includes("f_____") && front1.includes(" its meaning "), front1);
assert.ok(!/\bout\b|\bcontext\b|\bclue\b/.test(front1.replace(/<[^>]+>/g, "")), "fixed words must be blanked: " + front1);

// Trailing slot-like possessive, irregular inflection.
const w2 = "figure A out on one's own";
const s2 = "Anyone who decides to join the trip at the last minute will have to figure it out on their own.";
assert.ok(c.clozeHighlight(s2, w2).includes('<span class="example-highlight">figure it out on their own</span>'));

// No partial matching: a mismatched example is shown as-is.
assert.strictEqual(c.clozeMask("He criticized the rigidity of the bureaucrats.", "bear witness to A"), null);

console.log("cloze cases OK");
