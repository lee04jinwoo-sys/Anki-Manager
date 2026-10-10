"""Thread-safe single-slot job runner.

Anki/Gemini helpers in this project are blocking, so jobs run in a daemon thread
and publish progress through ``JobManager``. Only one job runs at a time, which
mirrors AnkiConnect's own single-threaded nature.
"""
from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable

from backend.schemas.jobs import (
    ActionResult,
    Candidates,
    JobState,
    JobStatus,
    LogEntry,
    LogLevel,
)

logger = logging.getLogger("AnkiManager.jobs")

BUSY_MESSAGE = "이미 다른 작업이 실행 중입니다."


class JobCancelled(Exception):
    """작업 함수가 취소 요청을 확인하고 중단할 때 던진다."""


class JobManager:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._state = JobState()
        self._cancel = threading.Event()

    # ---- reading -------------------------------------------------------
    def snapshot(self) -> JobState:
        with self._lock:
            return self._state.model_copy(deep=True)

    @property
    def is_running(self) -> bool:
        with self._lock:
            return self._state.is_running

    # ---- publishing ----------------------------------------------------
    def emit(self, message: str, progress: int | None = None, level: LogLevel = "info") -> None:
        with self._lock:
            s = self._state
            s.logs.append(
                LogEntry(time=time.strftime("%H:%M:%S"), message=message, level=level, progress=progress)
            )
            s.current_step = message
            if progress is not None and progress > 0:
                s.progress = progress
            if level == "error":
                s.status = "error"

    def set_candidates(self, candidates: Candidates) -> None:
        with self._lock:
            self._state.candidates = candidates

    def reset(self) -> None:
        with self._lock:
            if self._state.is_running:
                return
            self._state = JobState()

    # ---- cancelling ----------------------------------------------------
    def cancel(self) -> ActionResult:
        """취소를 요청한다. 실행 중인 단계는 끝까지 돌고, 다음 확인 지점에서 멈춘다."""
        with self._lock:
            if self._state.is_running:
                self._cancel.set()
                running = True
            elif self._state.status == "waiting_selection":
                self._state = JobState()
                return ActionResult(status="success", message="선택 대기를 취소했습니다.")
            else:
                return ActionResult(status="success", message="실행 중인 작업이 없습니다.")
        if running:
            self.emit("⏹ 취소 요청됨: 현재 단계가 끝나면 중단합니다.", level="warn")
        return ActionResult(status="success", message="취소를 요청했습니다. 현재 단계가 끝나면 중단합니다.")

    def raise_if_cancelled(self) -> None:
        if self._cancel.is_set():
            raise JobCancelled()

    # ---- running -------------------------------------------------------
    def start(
        self,
        name: str,
        fn: Callable[[], JobStatus | None],
        *,
        success_message: str | None = None,
        initial_progress: int = 15,
    ) -> ActionResult:
        """Run ``fn`` in the background.

        ``fn`` may return a final status (e.g. ``"waiting_selection"``); ``None`` means success.
        """
        with self._lock:
            if self._state.is_running:
                return ActionResult(status="error", message=BUSY_MESSAGE)
            self._state = JobState(
                is_running=True, source=name, progress=initial_progress, status="running"
            )
            self._cancel.clear()

        self.emit(f"[{name}] 작업 시작...", progress=initial_progress)

        def worker() -> None:
            try:
                final = fn()
                with self._lock:
                    if self._state.status != "error":
                        self._state.status = final or "success"
                if success_message and (final in (None, "success")):
                    self.emit(f"✅ {success_message}", progress=100, level="success")
                    with self._lock:
                        if self._state.status != "error":
                            self._state.status = "success"
            except JobCancelled:
                self.emit(f"⏹ [{name}] 작업이 취소되었습니다.", level="warn")
                with self._lock:
                    self._state.status = "cancelled"
            except Exception as exc:  # noqa: BLE001 - surface any job failure to the UI
                logger.exception("job %s failed", name)
                self.emit(f"❌ [{name}] 오류 발생: {exc}", level="error")
            finally:
                with self._lock:
                    self._state.is_running = False

        threading.Thread(target=worker, daemon=True, name=f"job:{name}").start()
        return ActionResult(status="success", message=f"{name} 작업을 시작했습니다.")


jobs = JobManager()
