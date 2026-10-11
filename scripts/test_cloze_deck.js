const fs = require("fs");
const core = require("./cloze_core.js");
const data = JSON.parse(fs.readFileSync(process.argv[2] || "/tmp/deck_dump.json", "utf8"));
let ok = 0, noSent = 0, noWord = 0; const fails = [];
for (const d of data) {
  const sents = core.clozeSplitSentences(d.sent);
  if (!sents.length) { noSent++; continue; }
  if (!core.clozeParse(d.word).length) { noWord++; fails.push({ nid: d.nid, word: d.word, why: "no fixed tokens", sent: sents[0] }); continue; }
  const hits = sents.filter(s => core.clozeMask(s, d.word) !== null).length;
  if (hits === sents.length) ok++;
  else fails.push({ nid: d.nid, word: d.word, why: hits === 0 ? "ALL_FAIL" : `partial ${hits}/${sents.length}`, sent: sents[0] });
}
console.log({ total: data.length, allSentencesMatch: ok, noSentence: noSent, noFixedTokens: noWord, issues: fails.length });
fs.writeFileSync("/tmp/cloze_fails.json", JSON.stringify(fails, null, 1));
const allFail = fails.filter(f => f.why === "ALL_FAIL");
console.log("ALL_FAIL:", allFail.length, " partial:", fails.filter(f => f.why.startsWith("partial")).length);
allFail.slice(0, 40).forEach(f => console.log(`[${f.nid}] ${f.word}  ||  ${f.sent.slice(0, 90)}`));
