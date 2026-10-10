import React from 'react'
import type { StatsOverview } from '../../types/stats'
import { ChartCard, SimpleTable } from './ChartCard'
import { useTooltip } from './Tooltip'
import { useWidth } from './useWidth'

const H = 170
const PAD = { top: 18, right: 8, bottom: 22, left: 34 }

const short = (iso: string) => {
  const [, m, d] = iso.split('-').map(Number)
  return `${m}/${d}`
}

/** 위쪽 모서리만 4px 둥근 막대 (아래는 기준선에 붙는다) */
function barPath(x0: number, x1: number, top: number, base: number) {
  const r = Math.min(4, (x1 - x0) / 2, base - top)
  return `M${x0},${base} V${top + r} Q${x0},${top} ${x0 + r},${top} H${x1 - r} Q${x1},${top} ${x1},${top + r} V${base} Z`
}

function niceMax(v: number) {
  if (v <= 0) return 10
  const p = 10 ** Math.floor(Math.log10(v))
  return Math.ceil(v / p) * p
}

export const ForecastChart: React.FC<{ forecast: StatsOverview['forecast'] }> = ({ forecast }) => {
  const { ref, width } = useWidth<HTMLDivElement>()
  const { node: tip, show, hide } = useTooltip()
  const max = niceMax(Math.max(...forecast.map((f) => f.due)))
  const innerW = width - PAD.left - PAD.right
  const innerH = H - PAD.top - PAD.bottom
  const slot = innerW / forecast.length
  const barW = Math.min(28, slot - 4)
  const y = (v: number) => PAD.top + innerH - (v / max) * innerH
  const total = forecast.slice(1, 8).reduce((a, f) => a + f.due, 0)
  const peak = forecast.reduce((a, f) => (f.due > a.due ? f : a), forecast[0]!)

  return (
    <ChartCard
      title="향후 14일 복습량"
      subtitle={`영어 덱 · 다음 7일 합계 ${total.toLocaleString()}장 · 최대 ${short(peak.date)} ${peak.due.toLocaleString()}장`}
      table={<SimpleTable head={['날짜', '복습 예정']} rows={forecast.map((f, i) => [i === 0 ? `${short(f.date)} (오늘 남음)` : short(f.date), f.due])} />}
    >
      <div ref={ref} className="w-full">
        <svg width={width} height={H} role="img" aria-label="향후 14일 날짜별 복습 예정 카드 수">
          {[0, 0.5, 1].map((t) => (
            <g key={t}>
              <line x1={PAD.left} x2={width - PAD.right} y1={y(max * t)} y2={y(max * t)} stroke="var(--viz-grid)" strokeWidth={1} />
              <text x={PAD.left - 6} y={y(max * t) + 3} textAnchor="end" fontSize={10} className="fill-apple-secondary">
                {Math.round(max * t)}
              </text>
            </g>
          ))}
          {forecast.map((f, i) => {
            const cx = PAD.left + slot * i + slot / 2
            const h = Math.max(0, PAD.top + innerH - y(f.due))
            return (
              <g key={f.date}>
                {/* 마우스 영역은 막대보다 넓게 */}
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
                        <div className="font-semibold">{i === 0 ? `오늘 (${short(f.date)})` : short(f.date)}</div>
                        <div className="text-apple-secondary">
                          {i === 0 ? '남은 복습' : '복습 예정'} {f.due.toLocaleString()}장
                        </div>
                      </>,
                    )
                  }
                  onMouseLeave={hide}
                />
                {h > 0 && (
                  <path
                    pointerEvents="none"
                    d={barPath(cx - barW / 2, cx + barW / 2, PAD.top + innerH - h, PAD.top + innerH)}
                    fill={i === 1 ? 'var(--viz-series-1)' : 'var(--viz-seq-2)'}
                  />
                )}
                {(i === 1 || f === peak) && f.due > 0 && (
                  <text x={cx} y={y(f.due) - 5} textAnchor="middle" fontSize={10} className="fill-apple-text" pointerEvents="none">
                    {f.due.toLocaleString()}
                  </text>
                )}
                {(i === 0 || i % 2 === 1) && (
                  <text x={cx} y={H - 6} textAnchor="middle" fontSize={10} className="fill-apple-secondary" pointerEvents="none">
                    {i === 0 ? '오늘' : i === 1 ? '내일' : short(f.date)}
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
