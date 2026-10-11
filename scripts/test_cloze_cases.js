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

// Loose fallback (only for notes with no strict match).
const hl = (s, w) => c.clozeHighlight(s, w, c.clozeNoteMode([s], w));
assert.ok(hl("She made a good point during the meeting.", "make a point").includes(">made a good point<"));
assert.ok(hl("I kept putting off the meeting.", "put A off").includes(">putting off<"));
assert.ok(hl("He's always cracking jokes and making people laugh.", "crack a joke").includes(">cracking jokes<"));
assert.ok(hl("He felt pressured to make a decision quickly.", "be pressured to V").includes("felt <span class=\"example-highlight\">pressured to</span>"));
assert.ok(hl("Skilled software engineers are heavily in demand.", "be in demand").includes(">are heavily in demand<"),
  "must not start inside \"software\"");
assert.ok(hl("I've been meaning to call you all week.", "have been meaning to V").includes(">'ve been meaning to<"));
assert.ok(hl("The siblings fought over who would sit in front.", "fight over A").includes(">fought over<"));

// A note with any strictly matching example never force-matches its other examples.
const notes = ["It will take a while to finish.", "I usually take a walk while listening to music."];
assert.strictEqual(c.clozeNoteMode(notes, "take a while"), "strict");
assert.strictEqual(c.clozeMask(notes[1], "take a while", "strict"), null);

console.log("cloze cases OK");
