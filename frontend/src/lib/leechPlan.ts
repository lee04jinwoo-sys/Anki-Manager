import type { LeechAction, LinkVocabItem } from '../types/dashboard'

export const LEECH_ACTIONS: { value: LeechAction; label: string; hint: string }[] = [
  { value: 'review_today', label: '다시 학습', hint: '오늘 다시 복습 (학습 기록 유지)' },
  { value: 'examples', label: '예문 추가', hint: 'AI 예문을 문장 덱에 추가하고 연결' },
  { value: 'promote', label: '청크 승격', hint: '후보 중 직접 골라 청크로 교체' },
  { value: 'reset', label: '초기화', hint: '새 카드로 (학습 기록이 끊김)' },
  { value: 'skip', label: '건너뛰기', hint: '이번엔 그대로' },
]

export const actionLabel = (a: LeechAction) => LEECH_ACTIONS.find((x) => x.value === a)!.label

/** 사용자가 고른 값 > 추천 > 다시 학습 */
export function choiceFor(item: LinkVocabItem, choices: Map<number, LeechAction>): LeechAction {
  return choices.get(item.note_id) ?? item.suggestion?.action ?? 'review_today'
}

export interface LeechPlan {
  batch: { note_id: number; word: string; meaning: string; action: LeechAction }[]
  promoteQueue: LinkVocabItem[]
  counts: Record<LeechAction, number>
}

/** 선택한 단어들을 일괄 실행분(다시 학습·초기화·예문)과 승격 대기열로 나눈다. 건너뛰기는 버린다. */
export function planActions(items: LinkVocabItem[], choices: Map<number, LeechAction>): LeechPlan {
  const counts: Record<LeechAction, number> = { review_today: 0, reset: 0, examples: 0, promote: 0, skip: 0 }
  const batch: LeechPlan['batch'] = []
  const promoteQueue: LinkVocabItem[] = []
  for (const it of items) {
    const action = choiceFor(it, choices)
    counts[action] += 1
    if (action === 'promote') promoteQueue.push(it)
    else if (action !== 'skip') batch.push({ note_id: it.note_id, word: it.word, meaning: it.meaning, action })
  }
  return { batch, promoteQueue, counts }
}
