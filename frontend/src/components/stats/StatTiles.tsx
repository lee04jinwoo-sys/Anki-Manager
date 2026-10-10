import React from 'react'
import type { StatsOverview } from '../../types/stats'

const fmt = (n: number) => n.toLocaleString()

const Tile: React.FC<{ label: string; value: React.ReactNode; sub: React.ReactNode }> = ({ label, value, sub }) => (
  <div className="rounded-apple border border-apple-border bg-apple-card p-4 shadow-apple-card">
    <div className="text-xs text-apple-secondary">{label}</div>
    <div className="mt-1 text-2xl font-semibold tracking-tight text-apple-text">{value}</div>
    <div className="mt-1 text-xs text-apple-secondary">{sub}</div>
  </div>
)

export const StatTiles: React.FC<{ data: StatsOverview }> = ({ data }) => {
  const { today, habit, retention_30d: ret, desired_retention: target } = data
  const rate = ret.all.rate
  const gap = rate !== null && target !== null ? rate - target : null

  return (
    <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
      <Tile
        label="오늘 리뷰 (전체 덱)"
        value={
          <>
            {fmt(today.reviews)}
            <span className="ml-1 text-sm font-normal text-apple-secondary">장 · {Math.round(today.minutes)}분</span>
          </>
        }
        sub={`30일 평균 ${fmt(Math.round(habit.avg_reviews_30d))}장 · ${Math.round(habit.avg_minutes_30d)}분`}
      />
      <Tile
        label="남은 복습 (영어)"
        value={
          <>
            {fmt(today.due_remaining)}
            <span className="ml-1 text-sm font-normal text-apple-secondary">장</span>
          </>
        }
        sub={`내일 ${fmt(today.due_tomorrow)}장 · 신규 대기 ${fmt(today.new_available)}장`}
      />
      <Tile
        label="30일 정답률 (영어, 리뷰 단위)"
        value={rate === null ? '–' : `${rate.toFixed(1)}%`}
        sub={
          <>
            {gap !== null && (
              <span className={gap < 0 ? 'text-apple-orange' : ''}>
                {gap < 0 ? '▼' : '▲'} 목표 {target}%보다 {Math.abs(gap).toFixed(1)}%p {gap < 0 ? '낮음' : '높음'}
                {' · '}
              </span>
            )}
            성숙 {ret.mature.rate ?? '–'}% · 새싹 {ret.young.rate ?? '–'}%
          </>
        }
      />
      <Tile
        label="연속 학습"
        value={
          <>
            {habit.current}
            <span className="ml-1 text-sm font-normal text-apple-secondary">일</span>
          </>
        }
        sub={`최장 ${habit.longest}일 · 최근 1년 중 ${habit.days_studied_365}일 공부`}
      />
    </div>
  )
}
