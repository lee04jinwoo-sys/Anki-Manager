import { describe, expect, it } from 'vitest'
import { statLabels } from './statLabels'

describe('statLabels', () => {
  it('names the Chinese decks in Chinese mode, never English or all decks', () => {
    const l = statLabels('zh')
    const all = [l.todayReviews, l.dueRemaining, l.retention30d, l.streak, l.heatmapScope]
    for (const label of all) {
      expect(label).toContain('중국어 덱')
      expect(label).not.toContain('영어')
      expect(label).not.toContain('전체 덱')
    }
  })

  it('names the English decks in English mode (stats are English-only, not all decks)', () => {
    const l = statLabels('en')
    const all = [l.todayReviews, l.dueRemaining, l.retention30d, l.streak, l.heatmapScope]
    for (const label of all) {
      expect(label).toContain('영어 덱')
      expect(label).not.toContain('전체 덱')
    }
    expect(l.retention30d).toBe('30일 정답률 (영어 덱, 리뷰 단위)')
  })
})
