"""Point [sound:...] tags at the media file that actually exists when only the letter case differs.

The server Anki (Linux, case-sensitive) holds lowercase media names, while some notes still
reference the mixed-case names they were created with on the Mac (case-insensitive), so those
sounds play nowhere but on the Mac. This rewrites only such tags; no audio is regenerated.

Run on the server against its AnkiConnect (fast, no tunnel), without deploying:
    ssh oracle-quant 'cd ~/anki-manager && .venv/bin/python - [--yes]' < scripts/fix_media_name_case.py
Dry run by default. Every changed field is logged (old/new) to data/backups/media-case-fix-*.jsonl
before it is written; --restore LOG --yes puts the old values back.
"""
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.getcwd())

from integrations.anki_connect import AnkiConnector  # noqa: E402

SOUND = re.compile(r"\[sound:([^\]]+)\]")


def ac(action, **params):
    return AnkiConnector.invoke(action, **params)


def plan():
    media = set(os.listdir(ac("getMediaDirPath")))
    by_lower = {}
    for m in media:
        by_lower.setdefault(m.lower(), []).append(m)
    ids = ac("findNotes", query="deck:*")
    changes, ambiguous = [], []
    for i in range(0, len(ids), 500):
        for n in ac("notesInfo", notes=ids[i:i + 500]):
            for field, v in n["fields"].items():
                old = v["value"]

                def fix(m):
                    name = m.group(1)
                    if name in media:
                        return m.group(0)
                    candidates = by_lower.get(name.lower(), [])
                    if len(candidates) == 1:
                        return f"[sound:{candidates[0]}]"
                    if len(candidates) > 1:
                        ambiguous.append((n["noteId"], name, candidates))
                    return m.group(0)

                new = SOUND.sub(fix, old)
                if new != old:
                    changes.append({"note_id": n["noteId"], "field": field, "old": old, "new": new})
    return changes, ambiguous


def main():
    yes = "--yes" in sys.argv
    if "--restore" in sys.argv:
        log = sys.argv[sys.argv.index("--restore") + 1]
        rows = [json.loads(line) for line in Path(log).read_text().splitlines() if line.strip()]
        print(f"{len(rows)} fields in {log}")
        if yes:
            for r in rows:
                ac("updateNoteFields", note={"id": r["note_id"], "fields": {r["field"]: r["old"]}})
            print("restored")
        return

    changes, ambiguous = plan()
    notes = {c["note_id"] for c in changes}
    print(f"{len(changes)} fields in {len(notes)} notes need a case fix; {len(ambiguous)} ambiguous (left alone)")
    for c in changes[:3]:
        print("   e.g.", c["note_id"], c["field"], c["old"][:70], "->", c["new"][:70])
    for a in ambiguous[:5]:
        print("   ambiguous", a)
    if not yes:
        print("dry run: nothing written; add --yes to write")
        return

    log = Path("data/backups") / f"media-case-fix-{datetime.now():%Y%m%d-%H%M%S}.jsonl"
    log.parent.mkdir(parents=True, exist_ok=True)
    with open(log, "a", encoding="utf-8") as f:
        for c in changes:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
            f.flush()
            ac("updateNoteFields", note={"id": c["note_id"], "fields": {c["field"]: c["new"]}})
    left, _ = plan()
    print(f"updated {len(changes)} fields; still mismatched after: {len(left)}; log: {log}")


if __name__ == "__main__":
    main()
