"""Obsidian Inbox -> Anki import (the only import source kept)."""
from __future__ import annotations

from backend.schemas.importer import ObsidianCommitRequest
from backend.schemas.jobs import ActionResult, Candidates, JobStatus
from backend.services import maintenance_service
from backend.services.jobs import jobs
from collectors.obsidian import ObsidianManager
from core.completer import run_note_completion


def start_extract() -> ActionResult:
    def run() -> JobStatus | None:
        jobs.emit("Obsidian Inbox 데이터 로드 중...", progress=30)
        data = ObsidianManager().fetch_inbox_content()
        if not data or (not data["vocab"] and not data["sentences"]):
            jobs.emit("가져올 Obsidian 데이터가 없습니다 (Inbox 비어있음).", level="warn")
            return "idle"

        vocab: list[dict[str, str]] = []
        for v in data["vocab"]:
            vocab.append({"단어": v, "뜻": ""} if isinstance(v, str) else v)
        jobs.set_candidates(Candidates(sentences=data["sentences"], vocab=vocab))
        jobs.emit(
            f"후보 추출 완료: 문장 {len(data['sentences'])}개, 단어 {len(vocab)}개. 화면에서 선택해주세요.",
            progress=100,
        )
        return "waiting_selection"

    return jobs.start("Obsidian 가져오기", run, initial_progress=10)


def start_commit(req: ObsidianCommitRequest) -> ActionResult:
    if not req.selected_sentences and not req.selected_vocab:
        return ActionResult(status="error", message="선택된 문장이나 단어가 없습니다.")

    vocab_dicts = [v.to_legacy() for v in req.selected_vocab]

    def run() -> None:
        jobs.emit(
            f"선택 항목 Anki 등록 시작 (문장 {len(req.selected_sentences)}개, 단어 {len(vocab_dicts)}개)",
            progress=20,
        )
        jobs.emit("AI 상세 보강(뜻, 예문, 품사, 번역) 및 Anki 카드 추가 중...", progress=30)
        run_note_completion(
            {"sentences": req.selected_sentences, "video_id": None, "segments": None},
            {"vocab": vocab_dicts, "video_id": None, "segments": None},
        )

        # 처리한 항목만 Inbox에서 제거한다 (선택하지 않은 항목은 보존).
        jobs.emit("Obsidian Inbox 정리 중...", progress=60)
        ObsidianManager().remove_processed_items(
            req.selected_sentences, [v["단어"] for v in vocab_dicts]
        )

        jobs.emit("오디오 생성 및 덱 정리 중...", progress=75)
        maintenance_service.run_steps_blocking(["audio", "deck_move"], base=75, span=20)

    return jobs.start(
        "Obsidian 가져오기 등록", run, success_message="Anki 등록 및 AI 보강이 완료되었습니다.", initial_progress=10
    )
