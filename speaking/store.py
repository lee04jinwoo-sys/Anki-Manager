"""SQLite persistence for speaking sessions, attempts, topic SRS, card candidates, and streaks."""
from __future__ import annotations

import datetime as dt
import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

from speaking.models import CardCandidate, SessionState, SpeakingMetrics, StepName

DB_PATH = Path(__file__).resolve().parents[1] / "data" / "speaking.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_date TEXT NOT NULL,
    track TEXT NOT NULL,
    topic_id TEXT NOT NULL,
    topic_prompt TEXT NOT NULL,
    warmup_prompts_json TEXT NOT NULL,
    mission_vocab_json TEXT NOT NULL,
    step TEXT NOT NULL,
    status TEXT NOT NULL,
    followup_question TEXT,
    created_at TEXT NOT NULL,
    completed_at TEXT
);

CREATE TABLE IF NOT EXISTS attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER,
    step TEXT NOT NULL,
    transcript TEXT NOT NULL,
    metrics_json TEXT NOT NULL,
    feedback_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS topic_srs (
    topic_id TEXT PRIMARY KEY,
    interval_days INTEGER NOT NULL,
    due_date TEXT NOT NULL,
    last_score REAL NOT NULL,
    review_count INTEGER NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS card_candidates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER,
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

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _row_to_session(self, row: sqlite3.Row) -> SessionState:
        return SessionState(
            id=row["id"],
            session_date=row["session_date"],
            track=row["track"],
            topic_id=row["topic_id"],
            topic_prompt=row["topic_prompt"],
            warmup_prompts=json.loads(row["warmup_prompts_json"]),
            mission_vocab=json.loads(row["mission_vocab_json"]),
            step=row["step"],
            status=row["status"],
            followup_question=row["followup_question"],
        )

    def create_session(
        self,
        session_date: str,
        track: str,
        topic_id: str,
        topic_prompt: str,
        warmup_prompts: List[str],
        mission_vocab: List[str],
    ) -> SessionState:
        with self._connect() as conn:
            # 이전 미완료 세션이 남아 있으면 취소 처리해 단일 활성 세션 보장
            conn.execute("UPDATE sessions SET status='cancelled', step='cancelled' WHERE status='active'")
            cur = conn.execute(
                """
                INSERT INTO sessions
                (session_date, track, topic_id, topic_prompt, warmup_prompts_json, mission_vocab_json,
                 step, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, 'warmup_1', 'active', ?)
                """,
                (
                    session_date,
                    track,
                    topic_id,
                    topic_prompt,
                    json.dumps(warmup_prompts, ensure_ascii=False),
                    json.dumps(mission_vocab, ensure_ascii=False),
                    _now_iso(),
                ),
            )
            row = conn.execute("SELECT * FROM sessions WHERE id=?", (cur.lastrowid,)).fetchone()
            return self._row_to_session(row)

    def get_active_session(self) -> Optional[SessionState]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM sessions WHERE status='active' ORDER BY id DESC LIMIT 1"
            ).fetchone()
            return self._row_to_session(row) if row else None

    def get_last_completed_track(self) -> Optional[str]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT track FROM sessions WHERE status='completed' ORDER BY id DESC LIMIT 1"
            ).fetchone()
            return row["track"] if row else None

    def get_recent_topic_ids(self, limit: int = 12) -> List[str]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT topic_id FROM sessions ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
            return [r["topic_id"] for r in rows]

    def advance_step(
        self,
        session_id: int,
        next_step: StepName,
        followup_question: Optional[str] = None,
    ) -> None:
        with self._connect() as conn:
            if followup_question is not None:
                conn.execute(
                    "UPDATE sessions SET step=?, followup_question=? WHERE id=?",
                    (next_step, followup_question, session_id),
                )
            else:
                conn.execute("UPDATE sessions SET step=? WHERE id=?", (next_step, session_id))

    def complete_session(self, session_id: int) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE sessions SET step='completed', status='completed', completed_at=? WHERE id=?",
                (_now_iso(), session_id),
            )

    def cancel_active_session(self) -> bool:
        with self._connect() as conn:
            cur = conn.execute(
                "UPDATE sessions SET step='cancelled', status='cancelled' WHERE status='active'"
            )
            return cur.rowcount > 0

    def has_completed_on(self, session_date: str) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM sessions WHERE session_date=? AND status='completed' LIMIT 1",
                (session_date,),
            ).fetchone()
            return row is not None

    def save_attempt(
        self,
        session_id: Optional[int],
        step: str,
        transcript: str,
        metrics: SpeakingMetrics,
        feedback: Dict[str, Any],
    ) -> int:
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO attempts (session_id, step, transcript, metrics_json, feedback_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    step,
                    transcript,
                    metrics.model_dump_json(),
                    json.dumps(feedback, ensure_ascii=False),
                    _now_iso(),
                ),
            )
            return int(cur.lastrowid)

    def get_attempt(self, session_id: int, step: str) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM attempts WHERE session_id=? AND step=? ORDER BY id DESC LIMIT 1",
                (session_id, step),
            ).fetchone()
            if not row:
                return None
            return {
                "id": row["id"],
                "step": row["step"],
                "transcript": row["transcript"],
                "metrics": json.loads(row["metrics_json"]),
                "feedback": json.loads(row["feedback_json"]),
            }

    def record_topic_outcome(self, topic_id: str, score: float, today: dt.date) -> str:
        """단순 SRS 규칙: 막힌 주제(<=6.5)는 3일 뒤, 보통(<=7.5)은 7일 뒤, 숙달(>=8)은 2배 이상 연장."""
        with self._connect() as conn:
            existing = conn.execute(
                "SELECT interval_days, review_count FROM topic_srs WHERE topic_id=?",
                (topic_id,),
            ).fetchone()
            prev_ivl = int(existing["interval_days"]) if existing else 0
            prev_cnt = int(existing["review_count"]) if existing else 0

            if score <= 6.5:
                next_ivl = 3
            elif score < 8.0:
                next_ivl = max(7, int(prev_ivl * 1.5)) if prev_ivl else 7
            else:
                next_ivl = max(14, prev_ivl * 2) if prev_ivl else 14

            due_date = (today + dt.timedelta(days=next_ivl)).isoformat()
            conn.execute(
                """
                INSERT INTO topic_srs (topic_id, interval_days, due_date, last_score, review_count, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(topic_id) DO UPDATE SET
                    interval_days=excluded.interval_days,
                    due_date=excluded.due_date,
                    last_score=excluded.last_score,
                    review_count=excluded.review_count,
                    updated_at=excluded.updated_at
                """,
                (topic_id, next_ivl, due_date, score, prev_cnt + 1, _now_iso()),
            )
            return due_date

    def get_due_topic_ids(self, today: dt.date) -> List[str]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT topic_id FROM topic_srs WHERE due_date <= ? ORDER BY due_date ASC",
                (today.isoformat(),),
            ).fetchall()
            return [r["topic_id"] for r in rows]

    def save_candidate(self, session_id: Optional[int], candidate: CardCandidate) -> int:
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO card_candidates (session_id, candidate_json, added_note_id, created_at)
                VALUES (?, ?, NULL, ?)
                """,
                (session_id, candidate.model_dump_json(), _now_iso()),
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
                "session_id": row["session_id"],
                "candidate": json.loads(row["candidate_json"]),
                "added_note_id": row["added_note_id"],
            }

    def list_session_candidates(self, session_id: int) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM card_candidates WHERE session_id=? ORDER BY id ASC",
                (session_id,),
            ).fetchall()
            return [
                {
                    "id": r["id"],
                    **json.loads(r["candidate_json"]),
                    "added_note_id": r["added_note_id"],
                }
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
                "SELECT DISTINCT session_date FROM sessions WHERE status='completed' ORDER BY session_date ASC"
            ).fetchall()
            total_row = conn.execute(
                "SELECT COUNT(*) AS cnt FROM sessions WHERE status='completed'"
            ).fetchone()
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
            "total_completed": int(total_row["cnt"]),
        }

    def recent_metrics_summary(self, days: int = 14, today: Optional[dt.date] = None) -> Dict[str, Any]:
        today = today or dt.date.today()
        cutoff = (today - dt.timedelta(days=days)).isoformat()
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT a.metrics_json
                FROM attempts a
                LEFT JOIN sessions s ON a.session_id = s.id
                WHERE a.step IN ('main_pass1', 'main_pass2', 'followup')
                  AND COALESCE(s.session_date, substr(a.created_at, 1, 10)) >= ?
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
