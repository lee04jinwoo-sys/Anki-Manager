"""질문 은행(DB)에서 질문을 순서대로 꺼내는 큐. Anki와 연결하지 않는다."""
from __future__ import annotations

from typing import List, Optional, Sequence, Tuple

from speaking.models import DailyQuestion, QueueCounts, SpeakingCard
from speaking.question_bank import DAILY_QUESTIONS
from speaking.store import SpeakingStore

LOOKAHEAD = 3  # 지금 질문 뒤로 미리 보여 줄 후보 수 (/skip 이 고를 수 있는 범위)


def _card_id(q: DailyQuestion) -> int:
    return int(q.id.split("_")[1])


def _topic_id(card_id: int) -> str:
    return f"daily_{int(card_id):03d}"


class DbQuestionDeck:
    def __init__(self, store: SpeakingStore, questions: Optional[Sequence[DailyQuestion]] = None) -> None:
        self.store = store
        self.questions = list(questions if questions is not None else DAILY_QUESTIONS)

    def _card(self, q: DailyQuestion) -> SpeakingCard:
        cid = _card_id(q)
        return SpeakingCard(
            card_id=cid,
            note_id=cid,
            topic_id=q.id,
            category=q.category,
            prompt_text=q.prompt,
            is_new=True,
        )

    def _pools(self) -> Tuple[List[DailyQuestion], List[DailyQuestion]]:
        status = self.store.question_statuses()
        opened = [q for q in self.questions if status.get(q.id) == "open"]
        unused = [q for q in self.questions if q.id not in status]
        if not opened and not unused:
            # 은행을 한 바퀴 다 돌았으면 처음부터 다시 시작한다.
            self.store.reset_question_progress()
            unused = list(self.questions)
        return opened, unused

    def get_deck_counts(self) -> QueueCounts:
        _, unused = self._pools()
        return QueueCounts(new_count=len(unused), total_in_deck=len(self.questions))

    def fetch_today_queue(self) -> Tuple[QueueCounts, List[SpeakingCard]]:
        opened, unused = self._pools()
        picked = opened + unused[:LOOKAHEAD]
        if picked and picked[0].id not in {q.id for q in opened}:
            self.store.set_question_status(picked[0].id, "open")
        counts = QueueCounts(new_count=len(unused), review_count=len(opened), total_in_deck=len(self.questions))
        return counts, [self._card(q) for q in picked]

    def answer_speaking_card(self, card_id: int, ease: int) -> None:
        self.store.set_question_status(_topic_id(card_id), "done")
