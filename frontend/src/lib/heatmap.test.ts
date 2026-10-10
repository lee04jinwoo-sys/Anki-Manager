import { describe, expect, it } from 'vitest'
import { buildWeeks, levelOf, levelThresholds, monthLabels } from './heatmap'

describe('levelThresholds / levelOf', () => {
  it('splits non-zero days into quartiles of the user own distribution', () => {
    const th = levelThresholds([0, 0, 100, 200, 300, 400, 500, 600, 700, 800])
    expect(th).toEqual([250, 450, 650])
    expect(levelOf(0, th)).toBe(0)
    expect(levelOf(100, th)).toBe(1)
    expect(levelOf(250, th)).toBe(1)
    expect(levelOf(251, th)).toBe(2)
    expect(levelOf(800, th)).toBe(4)
  })

  it('handles no activity', () => {
    expect(levelThresholds([0, 0])).toEqual([0, 0, 0])
    expect(levelOf(0, [0, 0, 0])).toBe(0)
  })
})

describe('buildWeeks', () => {
  it('starts columns on Sunday and pads the first week', () => {
    // 2026-10-07 is a Wednesday
    const days = ['2026-10-07', '2026-10-08', '2026-10-09', '2026-10-10', '2026-10-11'].map((date) => ({
      date,
      reviews: 1,
      minutes: 1,
    }))
    const weeks = buildWeeks(days)
    expect(weeks.length).toBe(2)
    expect(weeks[0]!.slice(0, 3)).toEqual([null, null, null])
    expect(weeks[0]![3]!.date).toBe('2026-10-07')
    expect(weeks[0]![6]!.date).toBe('2026-10-10')
    expect(weeks[1]![0]!.date).toBe('2026-10-11')
    expect(weeks[1]!.length).toBe(1)
  })
})

describe('monthLabels', () => {
  it('labels the first week column of each month', () => {
    const days = []
    const start = new Date(2026, 8, 27) // Sun 27 Sep 2026
    for (let i = 0; i < 14; i++) {
      const d = new Date(start)
      d.setDate(start.getDate() + i)
      const iso = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
      days.push({ date: iso, reviews: 0, minutes: 0 })
    }
    expect(monthLabels(buildWeeks(days))).toEqual([
      { col: 0, label: '9월' },
      { col: 1, label: '10월' },
    ])
  })
})
