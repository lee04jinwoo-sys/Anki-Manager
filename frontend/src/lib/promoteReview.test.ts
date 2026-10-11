import { describe, expect, it } from 'vitest'
import { buildPromoteRequests, mapWithConcurrency, type ReviewRow } from './promoteReview'
import type { CollocationCandidate } from '../types/corpus'

const cand = (chunk: string): CollocationCandidate =>
  ({ chunk, meaning: `${chunk}-뜻`, pos: 'v', tier: 't', rank: 1, example_1: 'e1', trans_1: 't1', example_2: 'e2', trans_2: 't2', explanation: 'x', frequency_score: null }) as CollocationCandidate

describe('mapWithConcurrency', () => {
  it('never runs more than the limit at once and keeps order', async () => {
    let active = 0
    let peak = 0
    const out = await mapWithConcurrency([1, 2, 3, 4, 5, 6, 7], 3, async (n) => {
      active++
      peak = Math.max(peak, active)
      await new Promise((r) => setTimeout(r, 5))
      active--
      if (n === 4) throw new Error('boom')
      return n * 10
    })
    expect(peak).toBe(3)
    expect(out.map((r) => (r.ok ? r.value : 'err'))).toEqual([10, 20, 30, 'err', 50, 60, 70])
  })
})

describe('buildPromoteRequests', () => {
  const rows: ReviewRow[] = [
    { noteId: 1, word: 'lurk', status: 'ready', candidates: [cand('lurk in the shadows'), cand('lurk behind A')], selected: 1, edits: {} },
    { noteId: 2, word: 'appraise', status: 'ready', candidates: [cand('appraise A critically')], selected: -1, edits: {} },
    { noteId: 3, word: 'dusk', status: 'loading', candidates: [], selected: 0, edits: {} },
    { noteId: 4, word: 'whisk', status: 'ready', candidates: [cand('whisk A together')], selected: 0, edits: { example_1: '고친 예문' } },
  ]

  it('uses the chosen candidate, skips "승격 안 함" and rows not loaded, applies edits', () => {
    const reqs = buildPromoteRequests(rows, { resetToNew: true, addSentences: false })
    expect(reqs.map((r) => [r.note_id, r.new_chunk])).toEqual([
      [1, 'lurk behind A'],
      [4, 'whisk A together'],
    ])
    expect(reqs[1]!.example_1).toBe('고친 예문')
    expect(reqs[0]).toMatchObject({ reset_to_new: true, add_sentences_to_deck: false, meaning: 'lurk behind A-뜻' })
  })
})
