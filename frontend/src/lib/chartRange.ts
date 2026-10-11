export type ForecastRange = '1m' | '3m' | '6m'
export type RetentionRange = '3m' | '6m' | '1y'

export const FORECAST_RANGES: { value: ForecastRange; label: string }[] = [
  { value: '1m', label: '1개월' },
  { value: '3m', label: '3개월' },
  { value: '6m', label: '6개월' },
]
export const RETENTION_RANGES: { value: RetentionRange; label: string; weeks: number }[] = [
  { value: '3m', label: '3개월', weeks: 13 },
  { value: '6m', label: '6개월', weeks: 26 },
  { value: '1y', label: '1년', weeks: 52 },
]

export interface ForecastBar {
  start: string
  end: string
  due: number
}

/** 1개월은 일별 30개, 3·6개월은 7일 합계 막대 */
export function forecastSeries(days: { date: string; due: number }[], range: ForecastRange): ForecastBar[] {
  if (range === '1m') return days.slice(0, 30).map((d) => ({ start: d.date, end: d.date, due: d.due }))
  const span = range === '3m' ? days.slice(0, 91) : days.slice(0, 182)
  const out: ForecastBar[] = []
  for (let i = 0; i < span.length; i += 7) {
    const w = span.slice(i, i + 7)
    out.push({ start: w[0]!.date, end: w[w.length - 1]!.date, due: w.reduce((a, d) => a + d.due, 0) })
  }
  return out
}
