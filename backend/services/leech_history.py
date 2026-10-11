"""Leech 처리 기록 (로컬 DB, Anki는 건드리지 않는다).

처리한 단어는 기본 Leech 목록에서 숨기고, 처리 후 오답이 RELAPSE_LAPSES 회 이상 늘면 '재발'로 다시 보여준다.
누적 오답 수를 지우지 않는 이유: 원래 난이도 기록과 재발 감지를 남기기 위해서다.
"""
from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import Any

DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "leech_treatments.db"
RELAPSE_LAPSES = 4  # 사용자 기준 (2026-10-11): 처리 후 오답 4회 → 재발


def _conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), timeout=5.0)
    conn.row_factory = sqlite3.Row
    conn.execute(
        "CREATE TABLE IF NOT EXISTS treatments ("
        " note_id INTEGER PRIMARY KEY, word TEXT, action TEXT, treated_at REAL, lapses_at INTEGER)"
    )
    return conn


def record(items: list[dict[str, Any]], treated_at: float | None = None) -> None:
    """items: [{note_id, word, action, lapses_at}] — 같은 단어를 다시 처리하면 기록을 바꾼다."""
    ts = treated_at or time.time()
    with _conn() as conn:
        conn.executemany(
            "INSERT OR REPLACE INTO treatments (note_id, word, action, treated_at, lapses_at) VALUES (?, ?, ?, ?, ?)",
            [(int(i["note_id"]), i.get("word", ""), i["action"], i.get("treated_at", ts), int(i.get("lapses_at", 0))) for i in items],
        )


def get_all() -> dict[int, dict[str, Any]]:
    with _conn() as conn:
        return {r["note_id"]: dict(r) for r in conn.execute("SELECT * FROM treatments")}


def status(row: dict[str, Any], current_lapses: int) -> dict[str, Any]:
    since = max(0, int(current_lapses) - int(row["lapses_at"]))
    return {
        "action": row["action"],
        "treated_at": row["treated_at"],
        "lapses_at": row["lapses_at"],
        "lapses_since": since,
        "relapsed": since >= RELAPSE_LAPSES,
    }
