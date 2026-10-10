export interface DayCell {
  date: string // YYYY-MM-DD (Anki 하루 경계 기준)
  reviews: number
  minutes: number
}

function quantile(sorted: number[], p: number): number {
  const pos = sorted.length * p
  if (Number.isInteger(pos) && pos > 0) return (sorted[pos - 1]! + sorted[pos]!) / 2
  return sorted[Math.floor(pos)]!
}

/** 공부한 날(리뷰 > 0)의 사분위수 → 1~4단계 경계. 본인 기록 대비 상대적인 강도다. */
export function levelThresholds(values: number[]): [number, number, number] {
  const nz = values.filter((v) => v > 0).sort((a, b) => a - b)
  if (nz.length === 0) return [0, 0, 0]
  return [quantile(nz, 0.25), quantile(nz, 0.5), quantile(nz, 0.75)]
}

export function levelOf(v: number, th: [number, number, number]): 0 | 1 | 2 | 3 | 4 {
  if (v <= 0) return 0
  if (v <= th[0]) return 1
  if (v <= th[1]) return 2
  if (v <= th[2]) return 3
  return 4
}

const parse = (iso: string) => {
  const [y, m, d] = iso.split('-').map(Number)
  return new Date(y!, m! - 1, d!)
}

/** 일요일 시작 주 단위 열. 첫 주는 앞을 null로 채운다. */
export function buildWeeks(days: DayCell[]): (DayCell | null)[][] {
  const weeks: (DayCell | null)[][] = []
  let current: (DayCell | null)[] = []
  days.forEach((day, i) => {
    const dow = parse(day.date).getDay()
    if (i === 0) current = Array(dow).fill(null)
    else if (dow === 0) {
      weeks.push(current)
      current = []
    }
    current.push(day)
  })
  if (current.length) weeks.push(current)
  return weeks
}

/** 각 열 첫 칸의 달이 앞 열과 달라지는 곳에 달 이름을 단다. */
export function monthLabels(weeks: (DayCell | null)[][]): { col: number; label: string }[] {
  const out: { col: number; label: string }[] = []
  let prev = -1
  weeks.forEach((week, col) => {
    const first = week.find((d) => d !== null)
    if (!first) return
    const m = parse(first.date).getMonth()
    if (m !== prev) out.push({ col, label: `${m + 1}월` })
    prev = m
  })
  return out
}
