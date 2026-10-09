"""Dashboard Router.

Aggregates Anki connectivity, English sub-deck detailed analytics (Remaining New,
Due, Mature/Young retention, Suspended), chronic leeches, and Obsidian inbox state.
"""
from __future__ import annotations

import logging
from typing import List
from fastapi import APIRouter

from backend.schemas.dashboard import (
    DashboardResponse,
    DeckCardCount,
    LeechSummaryItem,
    MaintenanceOverview,
    ObsidianInboxSummary,
)
from backend.services.jobs import jobs
from collectors.obsidian import ObsidianManager
from config import MODEL_VOCAB
from integrations.anki_connect import AnkiConnector

logger = logging.getLogger("AnkiManagerDashboard")
router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

# Focus specifically on English sub-decks per user guidelines
ENGLISH_DECK_TARGETS = [
    ("1. Language::1.1. English::Vocabulary", "Vocabulary"),
    ("1. Language::1.1. English::Sentence", "Sentence"),
    ("1. Language::1.1. English::Grammar", "Grammar"),
]


@router.get("", response_model=DashboardResponse)
@router.get("/", response_model=DashboardResponse)
def get_dashboard_summary() -> DashboardResponse:
    # 1. Anki 연결 상태 확인
    try:
        anki_version = str(AnkiConnector.invoke("version"))
    except Exception as e:
        logger.warning("Anki 연결 실패: %s", e)
        return DashboardResponse(
            connected=False,
            active_job=jobs.snapshot(),
        )

    # 2. English 하위 덱 상세 심층 통계 집계 (새 카드 잔여량, Due, Mature/Young, Suspended)
    deck_counts: List[DeckCardCount] = []
    try:
        all_deck_names = set(AnkiConnector.invoke("deckNames") or [])
        for deck_name, display_title in ENGLISH_DECK_TARGETS:
            if deck_name not in all_deck_names:
                continue

            # Query card distributions
            total_cards = len(AnkiConnector.invoke("findCards", query=f'deck:"{deck_name}"') or [])
            new_remaining = len(AnkiConnector.invoke("findCards", query=f'deck:"{deck_name}" is:new') or [])
            due_today = len(AnkiConnector.invoke("findCards", query=f'deck:"{deck_name}" is:due -is:suspended') or [])
            studied_today = len(AnkiConnector.invoke("findCards", query=f'deck:"{deck_name}" rated:1') or [])
            due_tomorrow = len(AnkiConnector.invoke("findCards", query=f'deck:"{deck_name}" prop:due=1') or [])
            due_7days = len(AnkiConnector.invoke("findCards", query=f'deck:"{deck_name}" prop:due<=7 prop:due>0') or [])
            learning = len(AnkiConnector.invoke("findCards", query=f'deck:"{deck_name}" is:learn') or [])
            mature_cards = AnkiConnector.invoke("findCards", query=f'deck:"{deck_name}" prop:ivl>=21') or []
            young_cards = AnkiConnector.invoke("findCards", query=f'deck:"{deck_name}" prop:ivl>0 prop:ivl<21') or []
            suspended = len(AnkiConnector.invoke("findCards", query=f'deck:"{deck_name}" is:suspended') or [])
            deck_leech_count = len(
                AnkiConnector.invoke("findCards", query=f'deck:"{deck_name}" (prop:ease<=1.3 OR prop:lapses>=4) -is:suspended') or []
            )

            mature = len(mature_cards)
            young = len(young_cards)
            reviewed_total = mature + young
            retention_rate = round((mature / reviewed_total * 100), 1) if reviewed_total > 0 else 0.0

            # True review recall retention rates
            today_fail = len(AnkiConnector.invoke("findCards", query=f'deck:"{deck_name}" rated:1:1') or [])
            today_retention = round(((studied_today - today_fail) / studied_today * 100), 1) if studied_today > 0 else 0.0

            m30_all = len(AnkiConnector.invoke("findCards", query=f'deck:"{deck_name}" rated:30') or [])
            m30_fail = len(AnkiConnector.invoke("findCards", query=f'deck:"{deck_name}" rated:30:1') or [])
            retention_30d = round(((m30_all - m30_fail) / m30_all * 100), 1) if m30_all > 0 else 0.0

            m30_mature_all = len(AnkiConnector.invoke("findCards", query=f'deck:"{deck_name}" rated:30 prop:ivl>=21') or [])
            m30_mature_fail = len(AnkiConnector.invoke("findCards", query=f'deck:"{deck_name}" rated:30:1 prop:ivl>=21') or [])
            mature_retention_30d = (
                round(((m30_mature_all - m30_mature_fail) / m30_mature_all * 100), 1)
                if m30_mature_all > 0
                else 0.0
            )

            # Sample reviewed cards to derive average interval, ease factor, and cumulative reps
            rev_ids = mature_cards + young_cards
            if rev_ids:
                step = max(1, len(rev_ids) // 250)
                sample_ids = rev_ids[::step][:250]
                sample_info = AnkiConnector.invoke("cardsInfo", cards=sample_ids) or []
                if sample_info:
                    avg_ivl_days = round(sum(c.get("interval", 0) for c in sample_info) / len(sample_info), 1)
                    avg_ivl_months = round(avg_ivl_days / 30.4375, 1)
                    avg_ease = round(sum(c.get("factor", 0) for c in sample_info) / (len(sample_info) * 10), 1)
                    avg_reps = sum(c.get("reps", 0) for c in sample_info) / len(sample_info)
                    total_reps_est = int(avg_reps * len(rev_ids))
                else:
                    avg_ivl_days, avg_ivl_months, avg_ease, total_reps_est = 0.0, 0.0, 0.0, 0
            else:
                avg_ivl_days, avg_ivl_months, avg_ease, total_reps_est = 0.0, 0.0, 0.0, 0

            deck_counts.append(
                DeckCardCount(
                    name=deck_name,
                    display_name=display_title,
                    total=total_cards,
                    new_remaining=new_remaining,
                    due_today=due_today,
                    studied_today=studied_today,
                    due_tomorrow=due_tomorrow,
                    due_7days=due_7days,
                    learning=learning,
                    mature=mature,
                    young=young,
                    suspended=suspended,
                    deck_leech_count=deck_leech_count,
                    avg_interval_days=avg_ivl_days,
                    avg_interval_months=avg_ivl_months,
                    avg_ease=avg_ease,
                    total_reps_est=total_reps_est,
                    today_retention=today_retention,
                    retention_30d=retention_30d,
                    mature_retention_30d=mature_retention_30d,
                    retention_rate=retention_rate,
                )
            )
    except Exception as e:
        logger.warning("English 덱 상세 통계 조회 실패: %s", e)

    # 3. 유지보수 대기 카드 카운트 (오디오 누락, 의미 누락)
    missing_audio = 0
    missing_fields = 0
    try:
        audio_ids = AnkiConnector.find_notes(f'note:"{MODEL_VOCAB}" "오디오:"')
        missing_audio = len(audio_ids)
    except Exception as e:
        logger.debug("오디오 누락 조회 실패: %s", e)

    try:
        field_ids = AnkiConnector.find_notes(f'note:"{MODEL_VOCAB}" "뜻:"')
        missing_fields = len(field_ids)
    except Exception as e:
        logger.debug("뜻 누락 조회 실패: %s", e)

    maintenance = MaintenanceOverview(
        missing_audio_count=missing_audio,
        missing_fields_count=missing_fields,
        total_needs_count=missing_audio + missing_fields,
    )

    # 4. Leech (망각/오답 카드) 현황
    leech_items: List[LeechSummaryItem] = []
    leech_total = 0
    try:
        leech_query = f'note:"{MODEL_VOCAB}" (prop:ease<=1.3 OR prop:lapses>=4) -is:suspended'
        leech_card_ids = AnkiConnector.invoke("findCards", query=leech_query) or []
        leech_total = len(leech_card_ids)

        if leech_card_ids:
            sample_ids = leech_card_ids[:8]
            cards_info = AnkiConnector.invoke("cardsInfo", cards=sample_ids) or []
            for c in cards_info:
                fields = c.get("fields", {})
                word = fields.get("단어", {}).get("value", "")
                meaning = fields.get("뜻", {}).get("value", "")
                ease_raw = c.get("factor", 1300)
                ease_val = round(ease_raw / 10.0, 1)
                leech_items.append(
                    LeechSummaryItem(
                        note_id=int(c.get("note", 0)),
                        card_id=int(c.get("cardId", 0)),
                        word=word,
                        meaning=meaning,
                        lapses=int(c.get("lapses", 0)),
                        ease=ease_val,
                        reps=int(c.get("reps", 0)),
                    )
                )
    except Exception as e:
        logger.warning("Leech 카드 조회 실패: %s", e)

    # 5. Obsidian Inbox 대기열 요약 (단어 및 문장 전수 집계)
    inbox_summary = ObsidianInboxSummary(available=False)
    try:
        mgr = ObsidianManager()
        data = mgr.fetch_inbox_content()
        if data:
            vocab_list = data.get("vocab", [])
            sentences_list = data.get("sentences", [])
            v_cnt = len(vocab_list)
            s_cnt = len(sentences_list)
            inbox_summary = ObsidianInboxSummary(
                vocab_count=v_cnt,
                sentence_count=s_cnt,
                total_count=v_cnt + s_cnt,
                available=True,
            )
    except Exception as e:
        logger.debug("Obsidian inbox 조회 건너뜀: %s", e)

    return DashboardResponse(
        connected=True,
        anki_version=anki_version,
        decks=deck_counts,
        maintenance=maintenance,
        leeches=leech_items,
        leech_total_count=leech_total,
        obsidian_inbox=inbox_summary,
        active_job=jobs.snapshot(),
    )
