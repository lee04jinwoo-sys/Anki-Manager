import React, { useState } from 'react'
import type { StatsOverview } from '../../types/stats'
import { ChartCard, LegendSwatch, RangeToggle, SimpleTable } from './ChartCard'
import { RETENTION_RANGES, type RetentionRange } from '../../lib/chartRange'
import { useTooltip } from './Tooltip'
import { useWidth } from './useWidth'

const H = 170
const PAD = { top: 14, right: 44, bottom: 22, left: 34 }

const short = (iso: string) => {
  const [, m, d] = iso.split('-').map(Number)
  return `${m}/${d}`
}

type Week = StatsOverview['weekly_retention'][number]
const SERIES = [
  { key: 'mature' as const, label: '성숙 카드 (간격 21일+)', color: 'var(--viz-series-1)' },
  { key: 'young' as const, label: '새싹 카드', color: 'var(--viz-series-2)' },
]

export const RetentionChart: React.FC<{ weeks: Week[]; target: number | null }> = ({ weeks: allWeeks, target }) => {
  const [range, setRange] = useState<RetentionRange>('6m')
  const weeks = allWeeks.slice(-RETENTION_RANGES.find((r) => r.value === range)!.weeks)
  const { ref, width } = useWidth<HTMLDivElement>()
  const { node: tip, show, hide } = useTooltip()
  const [hover, setHover] = useState<number | null>(null)

  const values = weeks.flatMap((w) => SERIES.map((s) => w[s.key].rate)).filter((v): v is number => v !== null)
  const lo = Math.floor((Math.min(...values, target ?? 100) - 3) / 5) * 5
  const hi = 100
  const innerW = width - PAD.left - PAD.right
  const innerH = H - PAD.top - PAD.bottom
  const x = (i: number) => PAD.left + (weeks.length === 1 ? innerW / 2 : (innerW * i) / (weeks.length - 1))
  const y = (v: number) => PAD.top + innerH - ((v - lo) / (hi - lo)) * innerH
  const ticks = [lo, Math.round((lo + hi) / 2), hi]

  // 값이 없는 주(리뷰 0회)에서는 선을 끊는다
  const path = (key: 'mature' | 'young') => {
    let d = ''
    let penDown = false
    weeks.forEach((w, i) => {
      const r = w[key].rate
      if (r === null) {
        penDown = false
        return
      }
      d += `${penDown ? 'L' : 'M'}${x(i)},${y(r)} `
      penDown = true
    })
    return d
  }

  const last = weeks[weeks.length - 1]
  const endLabels = (() => {
    if (!last) return []
    const items = SERIES.filter((s) => last[s.key].rate !== null)
      .map((s) => ({ key: s.key, text: `${last[s.key].rate}%`, y: y(last[s.key].rate!) }))
      .sort((a, b) => a.y - b.y)
    for (let i = 1; i < items.length; i++) {
      if (items[i]!.y - items[i - 1]!.y < 12) items[i]!.y = items[i - 1]!.y + 12
    }
    return items
  })()
  return (
    <ChartCard
      title="주간 정답률 추이"
      subtitle={`영어 덱 · 7일 단위 ${weeks.length}주 · 복습 리뷰 중 Again 이외 비율${target ? ` · 가로선은 목표 ${target}%` : ''}`}
      controls={<RangeToggle value={range} options={RETENTION_RANGES} onChange={setRange} />}
      legend={SERIES.map((s) => (
        <LegendSwatch key={s.key} color={s.color} label={s.label} line />
      ))}
      table={
        <SimpleTable
          head={['주 (끝나는 날)', '성숙 %', '새싹 %', '리뷰 수']}
          rows={weeks.map((w) => [short(w.week_end), w.mature.rate ?? '–', w.young.rate ?? '–', w.all.reviews])}
        />
      }
    >
      <div ref={ref} className="w-full">
        <svg width={width} height={H} role="img" aria-label="주간 정답률 추이, 성숙 카드와 새싹 카드">
          {ticks.map((t) => (
            <g key={t}>
              <line x1={PAD.left} x2={width - PAD.right} y1={y(t)} y2={y(t)} stroke="var(--viz-grid)" strokeWidth={1} />
              <text x={PAD.left - 6} y={y(t) + 3} textAnchor="end" fontSize={10} className="fill-apple-secondary">
                {t}%
              </text>
            </g>
          ))}
          {target !== null && (
            <g>
              <line x1={PAD.left} x2={width - PAD.right} y1={y(target)} y2={y(target)} stroke="var(--viz-neutral)" strokeWidth={1} />
              <text x={PAD.left + 4} y={y(target) - 4} fontSize={10} className="fill-apple-secondary">
                목표 {target}%
              </text>
            </g>
          )}
          {hover !== null && (
            <line x1={x(hover)} x2={x(hover)} y1={PAD.top} y2={PAD.top + innerH} stroke="var(--viz-neutral)" strokeWidth={1} />
          )}
          {SERIES.map((s) => (
            <g key={s.key}>
              <path d={path(s.key)} fill="none" stroke={s.color} strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />
              {hover !== null && weeks[hover]![s.key].rate !== null && (
                <circle cx={x(hover)} cy={y(weeks[hover]![s.key].rate!)} r={4} fill={s.color} stroke="var(--viz-surface)" strokeWidth={2} />
              )}
            </g>
          ))}
          {/* 마지막 주 직접 라벨: 서로 12px 이상 떨어뜨린다 */}
          {endLabels.map((l) => (
            <text key={l.key} x={x(weeks.length - 1) + 6} y={l.y + 3} fontSize={10} className="fill-apple-text">
              {l.text}
            </text>
          ))}
          {weeks.map((w, i) => (
            <g key={w.week_end}>
              {(weeks.length - 1 - i) % Math.ceil(weeks.length / 6) === 0 && (
                <text x={x(i)} y={H - 6} textAnchor="middle" fontSize={10} className="fill-apple-secondary">
                  {short(w.week_end)}
                </text>
              )}
              <rect
                x={x(i) - innerW / Math.max(1, weeks.length - 1) / 2}
                y={PAD.top}
                width={innerW / Math.max(1, weeks.length - 1)}
                height={innerH}
                fill="transparent"
                onMouseMove={(e) => {
                  setHover(i)
                  show(
                    e,
                    <>
                      <div className="font-semibold">{short(w.week_end)}까지 7일</div>
                      <div>성숙 {w.mature.rate ?? '–'}% ({w.mature.reviews.toLocaleString()}회)</div>
                      <div>새싹 {w.young.rate ?? '–'}% ({w.young.reviews.toLocaleString()}회)</div>
                    </>,
                  )
                }}
                onMouseLeave={() => {
                  setHover(null)
                  hide()
                }}
              />
            </g>
          ))}
        </svg>
      </div>
      {tip}
    </ChartCard>
  )
}
