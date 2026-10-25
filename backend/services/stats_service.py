"""Learning statistics for the dashboard.

Pure functions work on AnkiConnect revlog rows from ``cardReviews``:
``(id_ms, cid, usn, ease, ivl, lastIvl, factor, time_ms, type)`` where ``ease`` is the
button (1 = Again, 0 = manual entry) and ``type`` is 0 learn / 1 review / 2 relearn /
3 filtered / 4 manual. ``get_overview`` gathers the data from Anki.
"""
from __future__ import annotations

import datetime as dt
import time
from collections import defaultdict
from typing import Any, Iterable

from integrations.anki_connect import AnkiConnector

ENGLISH_PARENT = "1. Language::1.1. English"
ENGLISH_DECKS = [
    (f"{ENGLISH_PARENT}::Vocabulary", "Vocabulary"),
    (f"{ENGLISH_PARENT}::Sentence", "Sentence"),
    (f"{ENGLISH_PARENT}::Grammar", "Grammar"),
]
CHINESE_PARENT = "1. Language::1.2. Chinese"
CHINESE_DECKS = [
    (f"{CHINESE_PARENT}::Vocabulary", "Vocabulary"),
    (f"{CHINESE_PARENT}::Sentence", "Sentence"),
]
MATURE_IVL = 21
FORECAST_DAYS = 180  # 향후 복습량: 오늘 포함 180일 (일별). 화면에서 주 단위로 묶어 본다
RETENTION_WEEKS = 52  # 주간 정답률: 1년
DEFAULT_ROLLOVER = 4
LEECH_QUERY = "(prop:ease<=1.3 OR prop:lapses>=4) -is:suspended"

Row = tuple  # revlog row as returned by cardReviews


# ---- pure helpers ------------------------------------------------------
def day_key(ts_ms: int, rollover_hour: int) -> str:
    """Anki 하루 경계(새벽 rollover_hour시)를 적용한 로컬 날짜."""
    local = dt.datetime.fromtimestamp(ts_ms / 1000) - dt.timedelta(hours=rollover_hour)
    return local.date().isoformat()


def daily_activity(rows: Iterable[Row], rollover_hour: int) -> dict[str, dict[str, float]]:
    """날짜별 리뷰 수와 공부 시간(분). 수동 기록(ease 0: 초기화·일정 변경)은 뺀다."""
    out: dict[str, dict[str, float]] = {}
    for r in rows:
        if r[3] == 0:
            continue
        d = out.setdefault(day_key(r[0], rollover_hour), {"reviews": 0, "minutes": 0.0})
        d["reviews"] += 1
        d["minutes"] += r[7] / 60000
    for d in out.values():
        d["minutes"] = round(d["minutes"], 1)
    return out


def streaks(study_days: set[str], today: dt.date) -> dict[str, int]:
    """현재 연속 학습일(오늘 안 했으면 어제까지)과 최장 연속."""
    current = 0
    day = today if today.isoformat() in study_days else today - dt.timedelta(days=1)
    while day.isoformat() in study_days:
        current += 1
        day -= dt.timedelta(days=1)

    longest = run = 0
    prev: dt.date | None = None
    for d in sorted(dt.date.fromisoformat(s) for s in study_days):
        run = run + 1 if prev is not None and (d - prev).days == 1 else 1
        longest = max(longest, run)
        prev = d
    return {"current": current, "longest": longest}


def _rate(passed: int, total: int) -> dict[str, Any]:
    return {"reviews": total, "passed": passed, "rate": round(passed / total * 100, 1) if total else None}


def retention(rows: Iterable[Row]) -> dict[str, dict[str, Any]]:
    """복습(type 1) 리뷰 단위 정답률. Again(1)만 실패, 직전 간격 21일 이상이면 성숙."""
    cnt = {"young": [0, 0], "mature": [0, 0]}
    for r in rows:
        if r[8] != 1 or r[3] == 0:
            continue
        bucket = cnt["mature" if r[5] >= MATURE_IVL else "young"]
        bucket[1] += 1
        bucket[0] += r[3] > 1
    y, m = cnt["young"], cnt["mature"]
    return {"young": _rate(*y), "mature": _rate(*m), "all": _rate(y[0] + m[0], y[1] + m[1])}


def weekly_retention(rows: Iterable[Row], rollover_hour: int, today: dt.date, weeks: int = 12) -> list[dict[str, Any]]:
    """오늘로 끝나는 7일 단위 구간별 정답률 (오래된 주 → 최근 주)."""
    by_week: dict[int, list[Row]] = defaultdict(list)
    for r in rows:
        age = (today - dt.date.fromisoformat(day_key(r[0], rollover_hour))).days
        if 0 <= age < weeks * 7:
            by_week[age // 7].append(r)
    out = []
    for w in range(weeks - 1, -1, -1):
        ret = retention(by_week.get(w, []))
        out.append({"week_end": (today - dt.timedelta(days=7 * w)).isoformat(), **ret})
    return out


def infer_rollover_hour(rows: Iterable[Row], reference: dict[str, int]) -> int:
    """Anki가 집계한 날짜별 리뷰 수(getNumCardsReviewedByDay)와 가장 잘 맞는 하루 경계 시각."""
    if not reference:
        return DEFAULT_ROLLOVER
    # 로컬 시각(초)을 한 번만 계산하고, 후보 시각마다 정수 나눗셈으로 날짜를 낸다.
    epoch = dt.date(1970, 1, 1)
    ref = {(dt.date.fromisoformat(d) - epoch).days: n for d, n in reference.items()}
    lo, hi = min(ref) - 1, max(ref) + 1
    local_secs = []
    for r in rows:
        sec = r[0] // 1000
        local = sec + time.localtime(sec).tm_gmtoff
        if lo <= local // 86400 <= hi:
            local_secs.append(local)
    if not local_secs:
        return DEFAULT_ROLLOVER
    best, best_err = DEFAULT_ROLLOVER, None
    for h in [DEFAULT_ROLLOVER] + [x for x in range(24) if x != DEFAULT_ROLLOVER]:
        counts: dict[int, int] = defaultdict(int)
        shift = h * 3600
        for loc in local_secs:
            counts[(loc - shift) // 86400] += 1
        err = sum(abs(counts.get(d, 0) - n) for d, n in ref.items())
        if best_err is None or err < best_err:
            best, best_err = h, err
    return best


def heatmap(daily: dict[str, dict[str, float]], today: dt.date, days: int = 365) -> list[dict[str, Any]]:
    out = []
    for i in range(days - 1, -1, -1):
        d = (today - dt.timedelta(days=i)).isoformat()
        v = daily.get(d, {"reviews": 0, "minutes": 0.0})
        out.append({"date": d, "reviews": int(v["reviews"]), "minutes": float(v["minutes"])})
    return out


# ---- Anki access -------------------------------------------------------
def _multi_count(queries: list[str], action: str = "findCards") -> list[int]:
    actions = [{"action": action, "version": 6, "params": {"query": q}} for q in queries]
    res = AnkiConnector.invoke("multi", actions=actions) or []
    return [len(r.get("result") or []) if isinstance(r, dict) else len(r or []) for r in res]


def get_overview(now: float | None = None, lang: str = "en") -> dict[str, Any]:
    now = now or time.time()
    year_ago_ms = int((now - 366 * 86400) * 1000)

    is_chinese = (lang == "zh" or lang == "chinese")
    target_parent = CHINESE_PARENT if is_chinese else ENGLISH_PARENT
    target_decks = CHINESE_DECKS if is_chinese else ENGLISH_DECKS

    # 1. 해당 언어 덱 리뷰 기록 (선택된 언어 덱의 카드만 엄격히 격리 집계)
    deck_names = AnkiConnector.invoke("deckNames") or []
    target_deck_names = [d for d in deck_names if d == target_parent or d.startswith(target_parent + "::")]
    lang_rows: dict[str, list[Row]] = {}
    for deck in target_deck_names:
        rows = AnkiConnector.invoke("cardReviews", deck=deck, startID=year_ago_ms) or []
        lang_rows[deck] = rows

    lang_all = [r for rows in lang_rows.values() for r in rows]

    reference = dict(AnkiConnector.invoke("getNumCardsReviewedByDay") or [])
    rollover = infer_rollover_hour(lang_all, {d: n for d, n in list(reference.items())[:60]})
    today = dt.date.fromisoformat(day_key(int(now * 1000), rollover))

    # 잔디맵 및 공부 습관 지표 (선택된 언어 덱 전용)
    daily = daily_activity(lang_all, rollover)
    days = heatmap(daily, today)
    studied = {d["date"] for d in days if d["reviews"] > 0}
    last30 = days[-30:]

    # 2. 해당 언어 덱 정답률 (최근 30일)
    cutoff_30 = int((now - 30 * 86400) * 1000)
    lang_30 = [r for r in lang_all if r[0] >= cutoff_30]

    # 3. 덱별 구성·부하 (findCards 개수를 multi 한 번으로)
    deck_queries: list[str] = []
    for deck, _ in target_decks:
        q = f'deck:"{deck}"'
        deck_queries += [
            f"{q} is:new -is:suspended",
            f"{q} is:learn -is:suspended",
            f"{q} is:review -is:learn prop:ivl<{MATURE_IVL} -is:suspended",
            f"{q} is:review -is:learn prop:ivl>={MATURE_IVL} -is:suspended",
            f"{q} is:suspended",
            f"{q} is:due -is:suspended",
            f"{q} prop:due=1 -is:suspended",
        ]
    forecast_queries = [f'deck:"{target_parent}" is:due -is:suspended'] + [
        f'deck:"{target_parent}" prop:due={n} -is:suspended' for n in range(1, FORECAST_DAYS)
    ]
    counts = _multi_count(deck_queries + forecast_queries)
    deck_counts, forecast_counts = counts[: len(deck_queries)], counts[len(deck_queries):]
    # 만성 오답은 노트(단어) 단위로 센다 (findNotes는 조건에 맞는 카드가 있는 노트를 돌려준다)
    leech_notes = _multi_count([f'deck:"{deck}" {LEECH_QUERY}' for deck, _ in target_decks], action="findNotes")

    decks = []
    for i, (deck, label) in enumerate(target_decks):
        new, learning, young, mature, suspended, due_today, due_tomorrow = deck_counts[i * 7:(i + 1) * 7]
        rows = lang_rows.get(deck, [])
        rows_30 = [r for r in rows if r[0] >= cutoff_30]
        today_rows = [r for r in rows if day_key(r[0], rollover) == today.isoformat() and r[3] != 0]
        decks.append({
            "name": deck,
            "label": label,
            "composition": {"new": new, "learning": learning, "young": young, "mature": mature, "suspended": suspended},
            "total": new + learning + young + mature + suspended,
            "due_today": due_today,
            "due_tomorrow": due_tomorrow,
            "reviewed_today": len(today_rows),
            "retention_30d": retention(rows_30),
            "leech_notes": leech_notes[i],
        })

    today_entry = days[-1]
    return {
        "today": {
            "date": today.isoformat(),
            "reviews": today_entry["reviews"],
            "minutes": today_entry["minutes"],
            "due_remaining": forecast_counts[0] if forecast_counts else 0,
            "due_tomorrow": forecast_counts[1] if len(forecast_counts) > 1 else 0,
            "new_available": sum(d["composition"]["new"] for d in decks),
        },
        "habit": {
            **streaks(studied, today),
            "days_studied_365": len(studied),
            "avg_reviews_30d": round(sum(d["reviews"] for d in last30) / 30, 1),
            "avg_minutes_30d": round(sum(d["minutes"] for d in last30) / 30, 1),
        },
        "retention_30d": retention(lang_30),
        "weekly_retention": weekly_retention(lang_all, rollover, today, weeks=RETENTION_WEEKS),
        "forecast": [
            {"date": (today + dt.timedelta(days=n)).isoformat(), "due": c} for n, c in enumerate(forecast_counts)
        ],
        "heatmap": days,
        "decks": decks,
        "rollover_hour": rollover,
        "desired_retention": _desired_retention(target_decks[0][0]),
        "lang": "zh" if is_chinese else "en",
    }


def _desired_retention(deck_name: str | None = None) -> float | None:
    """FSRS 목표 정답률(%) — 지정 덱 옵션 기준. 없으면 None."""
    try:
        target = deck_name or ENGLISH_DECKS[0][0]
        cfg = AnkiConnector.invoke("getDeckConfig", deck=target) or {}
        value = cfg.get("desiredRetention")
        return round(value * 100, 1) if value else None
    except Exception:
        return None
