import React from 'react'
import type { DeckStats } from '../../types/stats'
import { LegendSwatch } from './ChartCard'
import { useTooltip } from './Tooltip'

const PARTS = [
  { key: 'new' as const, label: '신규', color: 'var(--viz-seq-1)' },
  { key: 'learning' as const, label: '학습 중', color: 'var(--viz-seq-2)' },
  { key: 'young' as const, label: '새싹', color: 'var(--viz-seq-3)' },
  { key: 'mature' as const, label: '성숙', color: 'var(--viz-seq-4)' },
  { key: 'suspended' as const, label: '보류', color: 'var(--viz-neutral)' },
]

const pct = (v: number | null) => (v === null ? '–' : `${v.toFixed(1)}%`)

export const DeckTable: React.FC<{ decks: DeckStats[]; target: number | null }> = ({ decks, target }) => {
  const { node: tip, show, hide } = useTooltip()
  return (
    <section className="rounded-apple border border-apple-border bg-apple-card p-5 shadow-apple-card">
      <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
        <div>
          <h2 className="text-sm font-semibold text-apple-text">덱별 현황</h2>
          <p className="text-xs text-apple-secondary">정답률은 최근 30일 복습 리뷰 기준(▼ 목표 미만) · 만성 오답은 Lapse 4회+ 또는 Ease 130% 이하인 단어(노트) 수</p>
        </div>
        <div className="flex flex-wrap gap-3 text-[11px] text-apple-secondary">
          {PARTS.map((p) => (
            <LegendSwatch key={p.key} color={p.color} label={p.label} />
          ))}
        </div>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[720px] text-left text-xs">
          <thead className="text-apple-secondary">
            <tr>
              <th className="py-2 font-medium">덱</th>
              <th className="py-2 font-medium">카드 구성</th>
              <th className="py-2 text-right font-medium">오늘 리뷰</th>
              <th className="py-2 text-right font-medium">남음 / 내일</th>
              <th className="py-2 text-right font-medium">30일 정답률</th>
              <th className="py-2 text-right font-medium">만성 오답</th>
            </tr>
          </thead>
          <tbody>
            {decks.map((d) => {
              const total = Math.max(1, d.total)
              const all = d.retention_30d.all.rate
              const below = all !== null && target !== null && all < target
              return (
                <tr key={d.name} className="border-t border-apple-border align-middle">
                  <td className="py-3 pr-3">
                    <div className="text-sm font-semibold text-apple-text">{d.label}</div>
                    <div className="text-apple-secondary">{d.total.toLocaleString()}장</div>
                  </td>
                  <td className="w-[38%] py-3 pr-4">
                    <div className="flex h-2.5 w-full gap-[2px] overflow-hidden rounded-full">
                      {PARTS.map((p) => {
                        const v = d.composition[p.key]
                        if (v === 0) return null
                        return (
                          <div
                            key={p.key}
                            style={{ width: `${(v / total) * 100}%`, background: p.color, minWidth: 3 }}
                            onMouseMove={(e) =>
                              show(
                                e,
                                <>
                                  <div className="font-semibold">
                                    {d.label} · {p.label}
                                  </div>
                                  <div className="text-apple-secondary">
                                    {v.toLocaleString()}장 ({((v / total) * 100).toFixed(1)}%)
                                  </div>
                                </>,
                              )
                            }
                            onMouseLeave={hide}
                          />
                        )
                      })}
                    </div>
                    <div className="mt-1 text-apple-secondary">
                      성숙 {((d.composition.mature / total) * 100).toFixed(0)}% · 신규 {d.composition.new.toLocaleString()}장
                    </div>
                  </td>
                  <td className="py-3 text-right font-mono text-apple-text">{d.reviewed_today.toLocaleString()}</td>
                  <td className="py-3 text-right font-mono text-apple-text">
                    {d.due_today.toLocaleString()} <span className="text-apple-secondary">/ {d.due_tomorrow.toLocaleString()}</span>
                  </td>
                  <td className="py-3 text-right font-mono text-apple-text">
                    <span className={below ? 'text-apple-orange' : ''}>
                      {below && '▼ '}
                      {pct(all)}
                    </span>
                    <div className="text-[11px] text-apple-secondary">
                      성숙 {pct(d.retention_30d.mature.rate)} · 새싹 {pct(d.retention_30d.young.rate)}
                    </div>
                  </td>
                  <td className="py-3 text-right font-mono text-apple-text">{d.leech_notes.toLocaleString()}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      {tip}
    </section>
  )
}
