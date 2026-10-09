"""Unified note maintenance: missing fields + audio + deck rules (+ optional steps)."""
from __future__ import annotations

from collections.abc import Callable

from backend.schemas.jobs import ActionResult
from backend.schemas.maintenance import DEFAULT_STEPS, StepId, StepInfo
from backend.services.jobs import jobs
from core.completer import run_universal_field_completion
from integrations.anki_connect import AnkiConnector
from integrations.audio import AnkiTTSFiller
from utils.cleaner import clean_duplicates
from utils.organizer import run_organizer
from utils.pos_automator import run_pos_automation


def _run_audio() -> None:
    AnkiTTSFiller.run_audio_addition()


def _run_fields() -> None:
    run_universal_field_completion()


def _run_deck_move() -> None:
    run_organizer()


def _run_pos() -> None:
    run_pos_automation()


def _run_duplicates() -> None:
    clean_duplicates()


_STEP_FUNCS: dict[StepId, Callable[[], None]] = {
    "fields": _run_fields,
    "audio": _run_audio,
    "deck_move": _run_deck_move,
    "pos": _run_pos,
    "duplicates": _run_duplicates,
}

STEP_CATALOG: list[StepInfo] = [
    StepInfo(id="fields", label="빈 필드 채우기", description="모든 노트 타입에서 누락된 필드를 AI로 완성합니다.", default=True),
    StepInfo(id="audio", label="오디오 채우기", description="오디오가 없는 노트에 TTS를 생성합니다.", default=True),
    StepInfo(id="deck_move", label="규칙별 덱 이동", description="카드 타입 규칙에 따라 올바른 덱으로 이동합니다.", default=True),
    StepInfo(id="pos", label="품사 자동 입력", description="비어 있는 품사 필드를 NLTK로 채웁니다.", default=False),
    StepInfo(id="duplicates", label="중복 정리", description="중복 노트를 정리합니다.", default=False),
]
_LABELS: dict[StepId, str] = {s.id: s.label for s in STEP_CATALOG}


def step_catalog() -> list[StepInfo]:
    return list(STEP_CATALOG)


def ordered_steps(selected: list[StepId]) -> list[StepId]:
    """실행 순서는 항상 카탈로그 순서를 따른다 (필드 -> 오디오 -> 이동 ...)."""
    return [s.id for s in STEP_CATALOG if s.id in selected]


def run_steps_blocking(steps: list[StepId], *, base: int = 15, span: int = 80) -> None:
    """선택된 정리 단계를 현재 스레드에서 순차 실행하며 진행률을 JobManager에 발행한다."""
    order = ordered_steps(steps)
    total = len(order)
    for i, step in enumerate(order):
        jobs.emit(f"{_LABELS[step]} 진행 중... ({i + 1}/{total})", progress=base + int(span * i / total))
        _STEP_FUNCS[step]()
        jobs.emit(f"{_LABELS[step]} 완료", progress=base + int(span * (i + 1) / total))


def start_maintenance(steps: list[StepId] | None = None) -> ActionResult:
    selected = steps or list(DEFAULT_STEPS)
    return jobs.start(
        "노트 정리",
        lambda: run_steps_blocking(selected),
        success_message="노트 정리가 완료되었습니다.",
    )


def start_sync() -> ActionResult:
    def run() -> None:
        jobs.emit("Anki Web 동기화 요청 중...", progress=50)
        AnkiConnector.invoke("sync")

    return jobs.start("Anki Web 동기화", run, success_message="Anki Web 동기화가 완료되었습니다.")
