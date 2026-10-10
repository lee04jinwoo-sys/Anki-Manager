"""통계 계산(순수 함수). revlog 행: (id_ms, cid, usn, ease, ivl, lastIvl, factor, time_ms, type)."""
import datetime as dt

from backend.services import stats_service as st

ROLL = 4  # Anki 하루 경계 (새벽 4시)


def ts(y, m, d, h=12, mi=0):
    return int(dt.datetime(y, m, d, h, mi).timestamp() * 1000)


def rev(when, ease=3, last_ivl=30, rtype=1, time_ms=6000):
    return (when, 1, 0, ease, 40, last_ivl, 2500, time_ms, rtype)


def test_day_key_respects_rollover():
    assert st.day_key(ts(2026, 10, 10, 3, 59), ROLL) == "2026-10-09"
    assert st.day_key(ts(2026, 10, 10, 4, 0), ROLL) == "2026-10-10"


def test_daily_counts_exclude_manual_entries_and_sum_minutes():
    rows = [rev(ts(2026, 10, 9), time_ms=60000), rev(ts(2026, 10, 9), time_ms=30000),
            rev(ts(2026, 10, 9), ease=0, rtype=4)]  # 수동 초기화 기록은 제외
    daily = st.daily_activity(rows, ROLL)
    assert daily == {"2026-10-09": {"reviews": 2, "minutes": 1.5}}


def test_streaks():
    today = dt.date(2026, 10, 10)
    days = {"2026-10-10", "2026-10-09", "2026-10-08", "2026-10-01", "2026-09-30", "2026-09-29", "2026-09-28"}
    s = st.streaks(days, today)
    assert s == {"current": 3, "longest": 4}
    # 오늘 아직 안 했으면 어제까지 이어진 연속을 현재 연속으로 본다
    s2 = st.streaks(days - {"2026-10-10"}, today)
    assert s2["current"] == 2


def test_retention_uses_review_type_only_and_splits_maturity():
    rows = [
        rev(ts(2026, 10, 1), ease=3, last_ivl=30),   # 성숙 통과
        rev(ts(2026, 10, 1), ease=1, last_ivl=30),   # 성숙 실패
        rev(ts(2026, 10, 1), ease=4, last_ivl=5),    # 새싹 통과
        rev(ts(2026, 10, 1), ease=1, last_ivl=-600, rtype=0),  # 학습 단계 → 제외
        rev(ts(2026, 10, 1), ease=0, rtype=4),       # 수동 → 제외
    ]
    r = st.retention(rows)
    assert r == {"young": {"reviews": 1, "passed": 1, "rate": 100.0},
                 "mature": {"reviews": 2, "passed": 1, "rate": 50.0},
                 "all": {"reviews": 3, "passed": 2, "rate": 66.7}}


def test_retention_empty_rate_is_none():
    assert st.retention([])["all"] == {"reviews": 0, "passed": 0, "rate": None}


def test_weekly_retention_buckets_by_week_ending_today():
    today = dt.date(2026, 10, 10)
    rows = [rev(ts(2026, 10, 10), ease=3), rev(ts(2026, 10, 2), ease=1), rev(ts(2026, 10, 3), ease=3)]
    weeks = st.weekly_retention(rows, ROLL, today, weeks=2)
    assert [w["week_end"] for w in weeks] == ["2026-10-03", "2026-10-10"]
    assert weeks[1]["mature"]["rate"] == 100.0       # 10/4~10/10
    assert weeks[0]["mature"]["reviews"] == 2         # 9/27~10/3
    assert weeks[0]["mature"]["rate"] == 50.0


def test_infer_rollover_hour_picks_best_match():
    rows = [rev(ts(2026, 10, 10, 2)), rev(ts(2026, 10, 10, 5)), rev(ts(2026, 10, 10, 13))]
    # 4시 경계: 02시는 전날 → 10/09:1, 10/10:2
    assert st.infer_rollover_hour(rows, {"2026-10-09": 1, "2026-10-10": 2}) == 4
    assert st.infer_rollover_hour([], {}) == 4  # 정보가 없으면 Anki 기본값


def test_heatmap_fills_365_days_ending_today():
    today = dt.date(2026, 10, 10)
    hm = st.heatmap({"2026-10-10": {"reviews": 5, "minutes": 2.0}}, today, days=365)
    assert len(hm) == 365
    assert hm[-1] == {"date": "2026-10-10", "reviews": 5, "minutes": 2.0}
    assert hm[0] == {"date": "2025-10-11", "reviews": 0, "minutes": 0.0}
