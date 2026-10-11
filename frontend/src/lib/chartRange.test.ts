import { describe, expect, it } from 'vitest'
import { forecastSeries } from './chartRange'

const days = Array.from({ length: 180 }, (_, i) => {
  const d = new Date(2026, 9, 10 + i)
  const iso = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
  return { date: iso, due: i + 1 }
})

describe('forecastSeries', () => {
  it('1개월 = 30 daily bars', () => {
    const s = forecastSeries(days, '1m')
    expect(s.length).toBe(30)
    expect(s[0]).toEqual({ start: '2026-10-10', end: '2026-10-10', due: 1 })
  })

  it('3개월 = 7-day sums for 91 days (13 bars)', () => {
    const s = forecastSeries(days, '3m')
    expect(s.length).toBe(13)
    expect(s[0]).toEqual({ start: '2026-10-10', end: '2026-10-16', due: 1 + 2 + 3 + 4 + 5 + 6 + 7 })
  })

  it('6개월 = all 180 days in weeks (last bar may be shorter)', () => {
    const s = forecastSeries(days, '6m')
    expect(s.length).toBe(26)
    expect(s.reduce((a, b) => a + b.due, 0)).toBe((180 * 181) / 2)
    expect(s[25]!.end).toBe(days[179]!.date)
  })
})
