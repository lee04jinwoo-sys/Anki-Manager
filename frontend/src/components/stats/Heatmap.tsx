import React, { useEffect, useMemo, useRef, useState } from 'react'
import type { HeatmapDay } from '../../types/stats'
import { buildWeeks, levelOf, levelThresholds, monthLabels } from '../../lib/heatmap'
import { useTooltip } from './Tooltip'
import { useWidth } from './useWidth'

const GAP = 3
const LEFT = 22 // weekday labels
const TOP = 16 // month labels
const LEVEL_FILL = ['var(--viz-empty)', 'var(--viz-seq-1)', 'var(--viz-seq-2)', 'var(--viz-seq-3)', 'var(--viz-seq-4)']
const WEEKDAYS: [number, string][] = [
  [1, '월'],
  [3, '수'],
  [5, '금'],
]

const dateLabel = (iso: string) => {
  const [y, m, d] = iso.split('-').map(Number)
  const dow = '일월화수목금토'[new Date(y!, m! - 1, d!).getDay()]
  return `${y}년 ${m}월 ${d}일 (${dow})`
}

export const Heatmap: React.FC<{ days: HeatmapDay[]; rolloverHour: number }> = ({ days, rolloverHour }) => {
  const [showTable, setShowTable] = useState(false)
  const scroller = useRef<HTMLDivElement>(null)
  const { ref: box, width: boxWidth } = useWidth<HTMLDivElement>(900)
  const { node: tip, show, hide } = useTooltip()

  const th = useMemo(() => levelThresholds(days.map((d) => d.reviews)), [days])
  const weeks = useMemo(() => buildWeeks(days), [days])
  const months = useMemo(() => monthLabels(weeks), [weeks])
  // 카드 폭에 맞춰 칸 크기를 정한다 (9~16px). 좁으면 가로 스크롤.
  const CELL = Math.max(9, Math.min(16, Math.floor((boxWidth - LEFT - 24) / Math.max(1, weeks.length)) - GAP))
  const STEP = CELL + GAP
  const width = LEFT + weeks.length * STEP + 24 // 마지막 달 라벨 여유
  const height = TOP + 7 * STEP

  useEffect(() => {
    // 최근 날짜가 보이도록 오른쪽 끝으로
    if (scroller.current) scroller.current.scrollLeft = scroller.current.scrollWidth
  }, [weeks.length, showTable])

  const total = days.reduce((a, d) => a + d.reviews, 0)
  const legend = [
    '리뷰 없음',
    `1–${Math.round(th[0])}장`,
    `${Math.round(th[0]) + 1}–${Math.round(th[1])}장`,
    `${Math.round(th[1]) + 1}–${Math.round(th[2])}장`,
    `${Math.round(th[2]) + 1}장 이상`,
  ]

  return (
    <section className="rounded-apple border border-apple-border bg-apple-card p-5 shadow-apple-card">
      <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
        <div>
          <h2 className="text-sm font-semibold text-apple-text">학습 잔디</h2>
          <p className="text-xs text-apple-secondary">
            최근 1년 전체 덱 리뷰 {total.toLocaleString()}장 · 하루 경계 새벽 {rolloverHour}시 · 색 단계는 공부한 날의 사분위
          </p>
        </div>
        <button
          type="button"
          onClick={() => setShowTable((v) => !v)}
          className="rounded-apple-sm border border-apple-border px-2 py-1 text-xs text-apple-secondary hover:bg-apple-subtle"
        >
          {showTable ? '잔디로 보기' : '표로 보기'}
        </button>
      </div>

      {showTable ? (
        <div className="max-h-72 overflow-y-auto">
          <table className="w-full text-left text-xs">
            <thead className="sticky top-0 bg-apple-card text-apple-secondary">
              <tr>
                <th className="py-1 font-medium">날짜</th>
                <th className="py-1 text-right font-medium">리뷰</th>
                <th className="py-1 text-right font-medium">시간(분)</th>
              </tr>
            </thead>
            <tbody className="font-mono text-apple-text">
              {[...days].reverse().map((d) => (
                <tr key={d.date} className="border-t border-apple-border">
                  <td className="py-1">{d.date}</td>
                  <td className="py-1 text-right">{d.reviews.toLocaleString()}</td>
                  <td className="py-1 text-right">{d.minutes}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <>
          <div ref={box}>
          <div ref={scroller} className="overflow-x-auto pb-1">
            <svg width={width} height={height} role="img" aria-label="최근 1년 일별 리뷰 수 잔디맵">
              {months.map((m) => (
                <text key={`${m.col}-${m.label}`} x={LEFT + m.col * STEP} y={10} className="fill-apple-secondary" fontSize={10}>
                  {m.label}
                </text>
              ))}
              {WEEKDAYS.map(([row, label]) => (
                <text key={label} x={0} y={TOP + row * STEP + CELL - 1} className="fill-apple-secondary" fontSize={9}>
                  {label}
                </text>
              ))}
              {weeks.map((week, col) =>
                week.map((day, row) =>
                  day ? (
                    <rect
                      key={day.date}
                      x={LEFT + col * STEP}
                      y={TOP + row * STEP}
                      width={CELL}
                      height={CELL}
                      rx={2}
                      fill={LEVEL_FILL[levelOf(day.reviews, th)]}
                      onMouseMove={(e) =>
                        show(
                          e,
                          <>
                            <div className="font-semibold">{dateLabel(day.date)}</div>
                            <div className="text-apple-secondary">
                              {day.reviews > 0 ? `리뷰 ${day.reviews.toLocaleString()}장 · ${Math.round(day.minutes)}분` : '공부 기록 없음'}
                            </div>
                          </>,
                        )
                      }
                      onMouseLeave={hide}
                    />
                  ) : null,
                ),
              )}
            </svg>
          </div>
          </div>
          <div className="mt-2 flex flex-wrap items-center gap-3 text-[11px] text-apple-secondary">
            {legend.map((label, i) => (
              <span key={label} className="inline-flex items-center gap-1.5">
                <span className="inline-block h-[11px] w-[11px] rounded-[2px]" style={{ background: LEVEL_FILL[i] }} />
                {label}
              </span>
            ))}
          </div>
        </>
      )}
      {tip}
    </section>
  )
}
