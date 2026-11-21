"""SQLite persistence for v2 Anki-native speaking queues, card attempts, audio paths, and candidates."""
from __future__ import annotations

import datetime as dt
import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

from speaking.models import CardCandidate, SpeakingMetrics

DB_PATH = Path(__file__).resolve().parents[1] / "data" / "speaking.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS daily_queues (
    session_date TEXT PRIMARY KEY,
    total_assigned INTEGER NOT NULL,
    completed_count INTEGER NOT NULL DEFAULT 0,
    active_card_id INTEGER,
    retry_mode INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    completed_at TEXT
);

CREATE TABLE IF NOT EXISTS card_attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_date TEXT NOT NULL,
    card_id INTEGER,
    note_id INTEGER,
    topic_id TEXT NOT NULL,
    prompt_text TEXT NOT NULL,
    attempt_num INTEGER NOT NULL,
    mode TEXT NOT NULL,
    transcript TEXT NOT NULL,
    audio_path TEXT,
    metrics_json TEXT NOT NULL,
    feedback_json TEXT NOT NULL,
    score REAL,
    ease INTEGER,
    created_at TEXT NOT NULL,
    rated_at TEXT
);

CREATE TABLE IF NOT EXISTS question_progress (
    topic_id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS card_candidates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER,
    session_date TEXT,
    attempt_id INTEGER,
    candidate_json TEXT NOT NULL,
    added_note_id INTEGER,
    created_at TEXT NOT NULL
);
"""


def _now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


class SpeakingStore:
    def __init__(self, db_path: Optional[Path] = None) -> None:
        self.db_path = Path(db_path) if db_path is not None else DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(_SCHEMA)
            self._migrate_candidates_table(conn)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _migrate_candidates_table(self, conn: sqlite3.Connection) -> None:
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(card_candidates)").fetchall()}
        if "session_date" not in cols:
            conn.execute("ALTER TABLE card_candidates ADD COLUMN session_date TEXT")
        if "attempt_id" not in cols:
            conn.execute("ALTER TABLE card_candidates ADD COLUMN attempt_id INTEGER")

    @staticmethod
    def _row_to_queue(row: sqlite3.Row) -> Dict[str, Any]:
        return {
            "session_date": row["session_date"],
            "total_assigned": int(row["total_assigned"]),
            "completed_count": int(row["completed_count"]),
            "active_card_id": row["active_card_id"],
            "retry_mode": bool(row["retry_mode"]),
            "status": row["status"],
            "created_at": row["created_at"],
            "completed_at": row["completed_at"],
        }

    def get_daily_queue(self, session_date: str) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM daily_queues WHERE session_date=?", (session_date,)
            ).fetchone()
            return self._row_to_queue(row) if row else None

    def upsert_daily_queue(
        self,
        session_date: str,
        total_assigned: int,
        active_card_id: Optional[int],
        status: str = "active",
        retry_mode: bool = False,
    ) -> Dict[str, Any]:
        with self._connect() as conn:
            existing = conn.execute(
                "SELECT * FROM daily_queues WHERE session_date=?", (session_date,)
            ).fetchone()
            if existing:
                new_total = max(int(existing["total_assigned"]), int(total_assigned))
                conn.execute(
                    """
                    UPDATE daily_queues
                    SET total_assigned=?, active_card_id=?, retry_mode=?, status=?
                    WHERE session_date=?
                    """,
                    (new_total, active_card_id, int(retry_mode), status, session_date),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO daily_queues
                    (session_date, total_assigned, completed_count, active_card_id, retry_mode, status, created_at)
                    VALUES (?, ?, 0, ?, ?, ?, ?)
                    """,
                    (session_date, total_assigned, active_card_id, int(retry_mode), status, _now_iso()),
                )
            row = conn.execute(
                "SELECT * FROM daily_queues WHERE session_date=?", (session_date,)
            ).fetchone()
            return self._row_to_queue(row)

    def set_queue_state(
        self,
        session_date: str,
        active_card_id: Optional[int],
        retry_mode: bool = False,
        increment_completed: bool = False,
        status: Optional[str] = None,
    ) -> Dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM daily_queues WHERE session_date=?", (session_date,)
            ).fetchone()
            if not row:
                raise RuntimeError(f"Queue for {session_date} does not exist")
            completed_count = int(row["completed_count"]) + (1 if increment_completed else 0)
            new_status = status or row["status"]
            completed_at = _now_iso() if new_status == "completed" else row["completed_at"]
            conn.execute(
                """
                UPDATE daily_queues
                SET active_card_id=?, retry_mode=?, completed_count=?, status=?, completed_at=?
                WHERE session_date=?
                """,
                (active_card_id, int(retry_mode), completed_count, new_status, completed_at, session_date),
            )
            updated = conn.execute(
                "SELECT * FROM daily_queues WHERE session_date=?", (session_date,)
            ).fetchone()
            return self._row_to_queue(updated)

    def save_card_attempt(
        self,
        session_date: str,
        card_id: Optional[int],
        note_id: Optional[int],
        topic_id: str,
        prompt_text: str,
        attempt_num: int,
        mode: str,
        transcript: str,
        audio_path: Optional[str],
        metrics: SpeakingMetrics,
        feedback: Dict[str, Any],
        score: Optional[float] = None,
    ) -> int:
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO card_attempts
                (session_date, card_id, note_id, topic_id, prompt_text, attempt_num, mode,
                 transcript, audio_path, metrics_json, feedback_json, score, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_date,
                    card_id,
                    note_id,
                    topic_id,
                    prompt_text,
                    attempt_num,
                    mode,
                    transcript,
                    audio_path,
                    metrics.model_dump_json(),
                    json.dumps(feedback, ensure_ascii=False),
                    score,
                    _now_iso(),
                ),
            )
            return int(cur.lastrowid)

    def mark_attempt_rated(self, attempt_id: int, ease: int) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE card_attempts SET ease=?, rated_at=? WHERE id=?",
                (ease, _now_iso(), attempt_id),
            )

    @staticmethod
    def _row_to_attempt(row: sqlite3.Row) -> Dict[str, Any]:
        metrics = json.loads(row["metrics_json"])
        feedback = json.loads(row["feedback_json"])
        return {
            "id": row["id"],
            "session_date": row["session_date"],
            "card_id": row["card_id"],
            "note_id": row["note_id"],
            "topic_id": row["topic_id"],
            "prompt_text": row["prompt_text"],
            "attempt_num": row["attempt_num"],
            "mode": row["mode"],
            "transcript": row["transcript"],
            "audio_path": row["audio_path"],
            "metrics": metrics,
            "wpm": metrics.get("wpm", 0.0),
            "duration_sec": metrics.get("duration_sec", 0.0),
            "filler_count": metrics.get("filler_count", 0),
            "long_pause_count": metrics.get("long_pause_count", 0),
            "feedback": feedback,
            "native_model": feedback.get("native_model", ""),
            "score": row["score"],
            "ease": row["ease"],
            "created_at": row["created_at"],
        }

    def question_statuses(self) -> Dict[str, str]:
        with self._connect() as conn:
            return {r["topic_id"]: r["status"] for r in conn.execute("SELECT topic_id, status FROM question_progress")}

    def set_question_status(self, topic_id: str, status: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO question_progress (topic_id, status, updated_at) VALUES (?, ?, ?)
                ON CONFLICT(topic_id) DO UPDATE SET status=excluded.status, updated_at=excluded.updated_at
                """,
                (topic_id, status, _now_iso()),
            )

    def reset_question_progress(self) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM question_progress")

    def count_rated_today(self, session_date: str) -> int:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COUNT(DISTINCT card_id) AS n FROM card_attempts WHERE session_date=? AND mode='card' AND ease IS NOT NULL",
                (session_date,),
            ).fetchone()
        return int(row["n"])

    def get_latest_attempt(self) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM card_attempts WHERE mode='card' ORDER BY id DESC LIMIT 1").fetchone()
            return self._row_to_attempt(row) if row else None

    def get_latest_attempt_for_card_today(
        self, session_date: str, card_id: int
    ) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM card_attempts
                WHERE session_date=? AND card_id=? AND mode='card'
                ORDER BY id DESC LIMIT 1
                """,
                (session_date, card_id),
            ).fetchone()
            return self._row_to_attempt(row) if row else None

    def list_card_history(
        self, card_id: int, limit: int = 5, rated_only: bool = True
    ) -> List[Dict[str, Any]]:
        clause = "AND ease IS NOT NULL" if rated_only else ""
        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT * FROM card_attempts
                WHERE card_id=? AND mode='card' {clause}
                ORDER BY id DESC LIMIT ?
                """,
                (card_id, limit),
            ).fetchall()
            return [self._row_to_attempt(r) for r in rows]

    def list_today_attempts(
        self, session_date: str, mode: str = "card"
    ) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM card_attempts
                WHERE session_date=? AND mode=?
                ORDER BY id ASC
                """,
                (session_date, mode),
            ).fetchall()
            return [self._row_to_attempt(r) for r in rows]

    def save_candidate(
        self,
        session_date: str,
        attempt_id: Optional[int],
        candidate: CardCandidate,
    ) -> int:
        norm_key = (candidate.kind, candidate.text.strip().lower())
        with self._connect() as conn:
            existing = conn.execute(
                "SELECT id, candidate_json FROM card_candidates WHERE session_date=?",
                (session_date,),
            ).fetchall()
            for r in existing:
                old = json.loads(r["candidate_json"])
                if (old.get("kind"), (old.get("text") or "").strip().lower()) == norm_key:
                    return int(r["id"])
            cur = conn.execute(
                """
                INSERT INTO card_candidates
                (session_id, session_date, attempt_id, candidate_json, added_note_id, created_at)
                VALUES (NULL, ?, ?, ?, NULL, ?)
                """,
                (session_date, attempt_id, candidate.model_dump_json(), _now_iso()),
            )
            return int(cur.lastrowid)

    def get_candidate(self, candidate_id: int) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM card_candidates WHERE id=?", (candidate_id,)
            ).fetchone()
            if not row:
                return None
            return {
                "id": row["id"],
                "session_date": row["session_date"],
                "attempt_id": row["attempt_id"],
                "candidate": json.loads(row["candidate_json"]),
                "added_note_id": row["added_note_id"],
            }

    def list_today_candidates(self, session_date: str) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM card_candidates WHERE session_date=? ORDER BY id ASC",
                (session_date,),
            ).fetchall()
            return [
                {
                    "id": r["id"],
                    **json.loads(r["candidate_json"]),
                    "added_note_id": r["added_note_id"],
                }
                for r in rows
            ]

    def list_candidates_for_attempt(self, attempt_id: int) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM card_candidates WHERE attempt_id=? ORDER BY id ASC", (attempt_id,)
            ).fetchall()
            return [
                {"id": r["id"], **json.loads(r["candidate_json"]), "added_note_id": r["added_note_id"]}
                for r in rows
            ]

    def mark_candidate_added(self, candidate_id: int, note_id: int) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE card_candidates SET added_note_id=? WHERE id=?",
                (note_id, candidate_id),
            )

    def compute_streaks(self, today: dt.date) -> Dict[str, int]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT session_date FROM daily_queues WHERE status='completed'
                UNION
                SELECT session_date FROM card_attempts WHERE mode='card' AND ease IS NOT NULL
                """
            ).fetchall()
        days = {r["session_date"] for r in rows}
        current = 0
        cursor = today if today.isoformat() in days else today - dt.timedelta(days=1)
        while cursor.isoformat() in days:
            current += 1
            cursor -= dt.timedelta(days=1)

        longest = run = 0
        prev: Optional[dt.date] = None
        for d in sorted(dt.date.fromisoformat(s) for s in days):
            run = run + 1 if prev is not None and (d - prev).days == 1 else 1
            longest = max(longest, run)
            prev = d
        return {
            "current": current,
            "longest": longest,
            "total_completed": len(days),
        }

    def recent_metrics_summary(
        self, days: int = 14, today: Optional[dt.date] = None
    ) -> Dict[str, Any]:
        today = today or dt.date.today()
        cutoff = (today - dt.timedelta(days=days)).isoformat()
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT metrics_json
                FROM card_attempts
                WHERE mode='card' AND session_date >= ?
                """,
                (cutoff,),
            ).fetchall()
        if not rows:
            return {
                "attempts_count": 0,
                "avg_wpm": 0.0,
                "avg_fillers": 0.0,
                "avg_long_pauses": 0.0,
            }
        metrics = [json.loads(r["metrics_json"]) for r in rows]
        n = len(metrics)
        return {
            "attempts_count": n,
            "avg_wpm": round(sum(m.get("wpm", 0.0) for m in metrics) / n, 1),
            "avg_fillers": round(sum(m.get("filler_count", 0) for m in metrics) / n, 1),
            "avg_long_pauses": round(sum(m.get("long_pause_count", 0) for m in metrics) / n, 1),
        }
