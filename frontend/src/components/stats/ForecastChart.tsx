import React, { useMemo, useState } from 'react'
import type { StatsOverview } from '../../types/stats'
import { FORECAST_RANGES, forecastSeries, type ForecastRange } from '../../lib/chartRange'
import { ChartCard, RangeToggle, SimpleTable } from './ChartCard'
import { useTooltip } from './Tooltip'
import { useWidth } from './useWidth'

const H = 190
const PAD = { top: 18, right: 8, bottom: 22, left: 40 }

const short = (iso: string) => {
  const [, m, d] = iso.split('-').map(Number)
  return `${m}/${d}`
}
const span = (b: { start: string; end: string }) => (b.start === b.end ? short(b.start) : `${short(b.start)}–${short(b.end)}`)

/** 위쪽 모서리만 둥근 막대 (아래는 기준선에 붙는다) */
function barPath(x0: number, x1: number, top: number, base: number) {
  const r = Math.min(4, (x1 - x0) / 2, base - top)
  return `M${x0},${base} V${top + r} Q${x0},${top} ${x0 + r},${top} H${x1 - r} Q${x1},${top} ${x1},${top + r} V${base} Z`
}

function niceMax(v: number) {
  if (v <= 0) return 10
  const p = 10 ** Math.floor(Math.log10(v))
  return Math.ceil(v / p) * p
}

export const ForecastChart: React.FC<{
  forecast: StatsOverview['forecast']
  language?: 'en' | 'zh'
}> = ({ forecast, language = 'en' }) => {
  const [range, setRange] = useState<ForecastRange>('3m')
  const { ref, width } = useWidth<HTMLDivElement>()
  const { node: tip, show, hide } = useTooltip()
  const bars = useMemo(() => forecastSeries(forecast, range), [forecast, range])
  const weekly = range !== '1m'
  const langLabel = language === 'zh' ? '중국어 덱' : '영어 덱'

  const max = niceMax(Math.max(...bars.map((b) => b.due)))
  const innerW = width - PAD.left - PAD.right
  const innerH = H - PAD.top - PAD.bottom
  const slot = innerW / bars.length
  const barW = Math.max(2, Math.min(28, slot - 3))
  const y = (v: number) => PAD.top + innerH - (v / max) * innerH
  const total = bars.reduce((a, b) => a + b.due, 0)
  const peak = bars.reduce((a, b) => (b.due > a.due ? b : a), bars[0]!)
  const labelEvery = Math.ceil(bars.length / 7)

  return (
    <ChartCard
      title="향후 복습량"
      subtitle={`${langLabel} · ${weekly ? '주별 합계' : '일별'} · 기간 합계 ${total.toLocaleString()}장 · 최대 ${span(peak)} ${peak.due.toLocaleString()}장`}
      controls={<RangeToggle value={range} options={FORECAST_RANGES} onChange={setRange} />}
      table={<SimpleTable head={[weekly ? '주' : '날짜', '복습 예정']} rows={bars.map((b) => [span(b), b.due])} />}
    >
      <div ref={ref} className="w-full">
        <svg width={width} height={H} role="img" aria-label={`향후 ${weekly ? '주별' : '일별'} 복습 예정 카드 수`}>
          {[0, 0.5, 1].map((t) => (
            <g key={t}>
              <line x1={PAD.left} x2={width - PAD.right} y1={y(max * t)} y2={y(max * t)} stroke="var(--viz-grid)" strokeWidth={1} />
              <text x={PAD.left - 6} y={y(max * t) + 3} textAnchor="end" fontSize={10} className="fill-apple-secondary">
                {Math.round(max * t).toLocaleString()}
              </text>
            </g>
          ))}
          {bars.map((b, i) => {
            const cx = PAD.left + slot * i + slot / 2
            const h = Math.max(0, PAD.top + innerH - y(b.due))
            return (
              <g key={b.start}>
                <rect
                  x={PAD.left + slot * i}
                  y={PAD.top}
                  width={slot}
                  height={innerH}
                  fill="transparent"
                  onMouseMove={(e) =>
                    show(
                      e,
                      <>
                        <div className="font-semibold">{span(b)}</div>
                        <div className="text-apple-secondary">
                          {i === 0 && !weekly ? '오늘 남은 복습' : '복습 예정'} {b.due.toLocaleString()}장
                          {weekly && ` · 하루 평균 ${Math.round(b.due / 7).toLocaleString()}장`}
                        </div>
                      </>,
                    )
                  }
                  onMouseLeave={hide}
                />
                {h > 0 && (
                  <path pointerEvents="none" d={barPath(cx - barW / 2, cx + barW / 2, PAD.top + innerH - h, PAD.top + innerH)} fill="var(--viz-seq-3)" />
                )}
                {b === peak && b.due > 0 && (
                  <text x={cx} y={y(b.due) - 5} textAnchor="middle" fontSize={10} className="fill-apple-text" pointerEvents="none">
                    {b.due.toLocaleString()}
                  </text>
                )}
                {i % labelEvery === 0 && (
                  <text x={cx} y={H - 6} textAnchor="middle" fontSize={10} className="fill-apple-secondary" pointerEvents="none">
                    {i === 0 ? (weekly ? '이번 주' : '오늘') : short(b.start)}
                  </text>
                )}
              </g>
            )
          })}
        </svg>
      </div>
      {tip}
    </ChartCard>
  )
}
