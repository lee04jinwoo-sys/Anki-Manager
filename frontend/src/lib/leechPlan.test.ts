import { describe, expect, it } from 'vitest'
import { choiceFor, planActions } from './leechPlan'
import type { LeechAction, LinkVocabItem } from '../types/dashboard'

const item = (note_id: number, action: LeechAction): LinkVocabItem => ({
  note_id,
  word: `w${note_id}`,
  meaning: `m${note_id}`,
  pos: 'v',
  link_count: 0,
  suggestion: { action, reason: 'r' },
})

describe('choiceFor', () => {
  it('uses the user choice, else the suggestion, else review_today', () => {
    const a = item(1, 'examples')
    expect(choiceFor(a, new Map())).toBe('examples')
    expect(choiceFor(a, new Map([[1, 'reset']]))).toBe('reset')
    expect(choiceFor({ ...a, suggestion: undefined }, new Map())).toBe('review_today')
  })
})

describe('planActions', () => {
  it('splits batch items from the promote queue and drops skips', () => {
    const items = [item(1, 'review_today'), item(2, 'reset'), item(3, 'examples'), item(4, 'promote'), item(5, 'skip')]
    const plan = planActions(items, new Map())
    expect(plan.batch.map((b) => [b.note_id, b.action])).toEqual([
      [1, 'review_today'],
      [2, 'reset'],
      [3, 'examples'],
    ])
    expect(plan.batch[0]).toEqual({ note_id: 1, word: 'w1', meaning: 'm1', action: 'review_today' })
    expect(plan.promoteQueue.map((p) => p.note_id)).toEqual([4])
    expect(plan.counts).toEqual({ review_today: 1, reset: 1, examples: 1, promote: 1, skip: 1 })
  })
})
