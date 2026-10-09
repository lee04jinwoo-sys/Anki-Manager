import React from 'react'
import {
  BookOpen,
  CheckCircle2,
  Clock,
  Flame,
  Layers,
  Activity,
  Award,
  Zap,
} from 'lucide-react'
import type { DeckCardCount } from '../types/dashboard'

interface DeckGridProps {
  decks: DeckCardCount[]
}

export const DeckGrid: React.FC<DeckGridProps> = ({ decks }) => {
  // Aggregate KPIs across all English sub-decks
  const totalCardsAll = decks.reduce((acc, d) => acc + d.total, 0)
  const totalStudiedToday = decks.reduce((acc, d) => acc + d.studied_today, 0)
  const totalDueToday = decks.reduce((acc, d) => acc + d.due_today, 0)
  const totalDueTomorrow = decks.reduce((acc, d) => acc + d.due_tomorrow, 0)
  const totalDue7Days = decks.reduce((acc, d) => acc + d.due_7days, 0)
  const totalNewRemaining = decks.reduce((acc, d) => acc + d.new_remaining, 0)
  const totalRepsEst = decks.reduce((acc, d) => acc + d.total_reps_est, 0)

  // Weighted/Average Real Recall Retention across English decks
  const avgTodayRetention =
    totalStudiedToday > 0
      ? (
          decks.reduce(
            (acc, d) => acc + d.today_retention * d.studied_today,
            0,
          ) / totalStudiedToday
        ).toFixed(1)
      : '0.0'

  const avg30dRetention =
    decks.length > 0
      ? (
          decks.reduce((acc, d) => acc + d.retention_30d, 0) / decks.length
        ).toFixed(1)
      : '0.0'

  const avgMatureRetention =
    decks.length > 0
      ? (
          decks.reduce((acc, d) => acc + d.mature_retention_30d, 0) /
          decks.length
        ).toFixed(1)
      : '0.0'

  return (
    <div className="bg-apple-card border border-apple-border rounded-apple p-5 shadow-apple-card space-y-5">
      {/* 1. Header Section */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
        <div className="flex items-center gap-2">
          <BookOpen className="w-4 h-4 text-apple-secondary" />
          <h2 className="text-sm font-semibold text-apple-text tracking-tight">
            English 핵심 덱 통합 분석
          </h2>
          <span className="text-xs text-apple-secondary font-mono px-2 py-0.5 rounded-full bg-apple-bg border border-apple-border">
            Vocabulary · Sentence · Grammar
          </span>
        </div>
        <div className="text-xs text-apple-secondary font-mono flex items-center gap-2.5">
          <span>영어 전체:</span>
          <span className="text-apple-text font-semibold">
            {totalCardsAll.toLocaleString()}장
          </span>
          <span className="text-apple-borderStrong">|</span>
          <span>누적 복습:</span>
          <span className="text-apple-text font-semibold">
            약 {totalRepsEst.toLocaleString()}회
          </span>
        </div>
      </div>

      {/* 2. Top Macro Aggregation Strip (전체 덱 합산 KPI & Retention 스트립) */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2.5 p-3 rounded-apple-sm bg-apple-subtle/70 border border-apple-border/80">
        {/* Metric 1: Today Retention Rate (가장 중요한 복습 정답률) */}
        <div className="space-y-0.5">
          <div className="text-[10px] text-apple-secondary flex items-center gap-1">
            <Zap className="w-3 h-3 text-apple-green" />
            <span>금일 정답률 (Retention)</span>
          </div>
          <div className="text-base font-bold font-mono text-apple-green tracking-tight">
            {avgTodayRetention}%
            <span className="text-[10px] text-apple-secondary font-normal ml-1">
              ({totalStudiedToday}장 중)
            </span>
          </div>
        </div>

        {/* Metric 2: 30-Day Mature Retention Rate & Overall 30d */}
        <div className="space-y-0.5">
          <div className="text-[10px] text-apple-secondary flex items-center gap-1">
            <Award className="w-3 h-3 text-apple-green" />
            <span>성숙 유지율 (Mature Ret.)</span>
          </div>
          <div className="text-base font-bold font-mono text-apple-green tracking-tight">
            {avgMatureRetention}%
            <span className="text-[10px] text-apple-secondary font-normal ml-1">
              (30일 전체 {avg30dRetention}%)
            </span>
          </div>
        </div>

        {/* Metric 3: Today Studied Volume */}
        <div className="space-y-0.5">
          <div className="text-[10px] text-apple-secondary flex items-center gap-1">
            <CheckCircle2 className="w-3 h-3 text-apple-blue" />
            <span>오늘 복습 완료</span>
          </div>
          <div className="text-base font-bold font-mono text-apple-text tracking-tight">
            {totalStudiedToday.toLocaleString()}
            <span className="text-[10px] text-apple-secondary font-normal ml-0.5">
              장
            </span>
          </div>
        </div>

        {/* Metric 4: Due Today & Tomorrow */}
        <div className="space-y-0.5">
          <div className="text-[10px] text-apple-secondary flex items-center gap-1">
            <Clock className="w-3 h-3 text-apple-orange" />
            <span>당일 잔여 / 내일 예정</span>
          </div>
          <div className="text-base font-bold font-mono text-apple-text tracking-tight">
            <span
              className={
                totalDueToday > 0 ? 'text-apple-orange' : 'text-apple-text'
              }
            >
              {totalDueToday}
            </span>
            <span className="text-apple-secondary mx-1 font-normal text-xs">
              /
            </span>
            <span>{totalDueTomorrow}장</span>
          </div>
        </div>

        {/* Metric 5: 7-Day Workload */}
        <div className="space-y-0.5">
          <div className="text-[10px] text-apple-secondary flex items-center gap-1">
            <Activity className="w-3 h-3 text-apple-secondary" />
            <span>7일간 복습 부하</span>
          </div>
          <div className="text-base font-bold font-mono text-apple-text tracking-tight">
            {totalDue7Days.toLocaleString()}
            <span className="text-[10px] text-apple-secondary font-normal ml-0.5">
              장
            </span>
          </div>
        </div>

        {/* Metric 6: Remaining New Cards */}
        <div className="space-y-0.5">
          <div className="text-[10px] text-apple-secondary flex items-center gap-1">
            <Layers className="w-3 h-3 text-apple-blue" />
            <span>미학습 신규</span>
          </div>
          <div
            className={`text-base font-bold font-mono tracking-tight ${
              totalNewRemaining > 0 ? 'text-apple-blue' : 'text-apple-text'
            }`}
          >
            {totalNewRemaining.toLocaleString()}
            <span className="text-[10px] text-apple-secondary font-normal ml-0.5">
              {totalNewRemaining > 0 ? '대기' : '소진 완료'}
            </span>
          </div>
        </div>
      </div>

      {/* 3. Per-Deck Cockpit Cards Grid */}
      {decks.length === 0 ? (
        <div className="text-center py-12 text-xs text-apple-secondary">
          English 덱 데이터를 불러오지 못했습니다.
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          {decks.map((deck) => {
            const hasNew = deck.new_remaining > 0
            const hasDue = deck.due_today > 0

            // Distribution bar proportions
            const total = deck.total > 0 ? deck.total : 1
            const maturePct = Math.min(
              100,
              Math.max(0, (deck.mature / total) * 100),
            )
            const youngPct = Math.min(
              100,
              Math.max(0, (deck.young / total) * 100),
            )
            const newPct = Math.min(
              100,
              Math.max(0, (deck.new_remaining / total) * 100),
            )
            const suspendedPct = Math.min(
              100,
              Math.max(0, (deck.suspended / total) * 100),
            )

            return (
              <div
                key={deck.name}
                className="bg-apple-subtle/50 border border-apple-border hover:border-apple-borderStrong rounded-apple-sm p-4 transition-all shadow-apple-subtle flex flex-col justify-between space-y-3.5"
              >
                {/* Header */}
                <div className="flex items-start justify-between">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-base font-bold text-apple-text tracking-tight">
                        {deck.display_name}
                      </span>
                      {hasNew ? (
                        <span className="text-[10px] font-mono font-medium px-1.5 py-0.2 rounded bg-apple-blue/20 text-apple-blue border border-apple-blue/30">
                          +{deck.new_remaining} New
                        </span>
                      ) : (
                        <span className="text-[10px] font-mono text-apple-secondary px-1.5 py-0.2 rounded bg-apple-bg border border-apple-border">
                          New 0
                        </span>
                      )}
                    </div>
                    <div className="text-[11px] font-mono text-apple-secondary truncate max-w-[200px] mt-0.5">
                      {deck.name.replace('1. Language::1.1. English::', '')}
                    </div>
                  </div>
                  <div className="text-right">
                    <span className="text-xs font-mono font-semibold text-apple-text bg-apple-card px-2 py-0.5 rounded border border-apple-border">
                      {deck.total.toLocaleString()}장
                    </span>
                  </div>
                </div>

                {/* Section A: True Recall Retention Rate Profile (가장 중요한 기억 유지율) */}
                <div className="p-2.5 rounded-apple-sm bg-apple-card border border-apple-border">
                  <div className="text-[10px] font-medium text-apple-secondary uppercase tracking-wider mb-1.5 flex items-center justify-between">
                    <span>기억 유지율 (Retention Rate)</span>
                    <span className="font-mono text-[10px] text-apple-secondary">
                      30일 평균 {deck.retention_30d}%
                    </span>
                  </div>
                  <div className="grid grid-cols-3 gap-1.5 text-center">
                    {/* Today Retention */}
                    <div className="p-1 rounded bg-apple-bg/70 border border-apple-border/50">
                      <div className="text-[10px] text-apple-secondary">
                        금일 정답률
                      </div>
                      <div className="text-xs font-mono font-bold text-apple-green mt-0.5">
                        {deck.today_retention > 0
                          ? `${deck.today_retention}%`
                          : '-'}
                      </div>
                      <div className="text-[9px] text-apple-secondary font-mono">
                        ({deck.studied_today}장 복습)
                      </div>
                    </div>

                    {/* 30-Day Retention */}
                    <div className="p-1 rounded bg-apple-bg/70 border border-apple-border/50">
                      <div className="text-[10px] text-apple-secondary">
                        30일 전체
                      </div>
                      <div className="text-xs font-mono font-bold text-apple-text mt-0.5">
                        {deck.retention_30d}%
                      </div>
                      <div className="text-[9px] text-apple-secondary font-mono">
                        최근 1개월
                      </div>
                    </div>

                    {/* Mature Retention (Gold Standard) */}
                    <div className="p-1 rounded bg-apple-bg/70 border border-apple-border/50">
                      <div className="text-[10px] text-apple-secondary">
                        성숙 기억 유지
                      </div>
                      <div className="text-xs font-mono font-bold text-apple-green mt-0.5">
                        {deck.mature_retention_30d}%
                      </div>
                      <div className="text-[9px] text-apple-secondary font-mono">
                        21일+ 성숙군
                      </div>
                    </div>
                  </div>
                </div>

                {/* Section B: Daily & Weekly Workload Forecast (4 columns) */}
                <div>
                  <div className="text-[10px] font-medium text-apple-secondary uppercase tracking-wider mb-1">
                    학습 부하 및 일정
                  </div>
                  <div className="grid grid-cols-4 gap-1.5 p-2 rounded bg-apple-card border border-apple-border text-center">
                    <div>
                      <div className="text-[10px] text-apple-secondary">
                        금일 완료
                      </div>
                      <div className="text-xs font-mono font-bold text-apple-green mt-0.5">
                        {deck.studied_today.toLocaleString()}
                      </div>
                    </div>
                    <div>
                      <div className="text-[10px] text-apple-secondary">
                        당일 잔여
                      </div>
                      <div
                        className={`text-xs font-mono font-bold mt-0.5 ${
                          hasDue ? 'text-apple-orange' : 'text-apple-text'
                        }`}
                      >
                        {deck.due_today.toLocaleString()}
                      </div>
                    </div>
                    <div>
                      <div className="text-[10px] text-apple-secondary">
                        내일 예정
                      </div>
                      <div className="text-xs font-mono font-bold text-apple-text mt-0.5">
                        {deck.due_tomorrow.toLocaleString()}
                      </div>
                    </div>
                    <div>
                      <div className="text-[10px] text-apple-secondary">
                        7일간 누적
                      </div>
                      <div className="text-xs font-mono font-bold text-apple-text mt-0.5">
                        {deck.due_7days.toLocaleString()}
                      </div>
                    </div>
                  </div>
                </div>

                {/* Section C: Memory Strength & Stability (3 columns) */}
                <div>
                  <div className="text-[10px] font-medium text-apple-secondary uppercase tracking-wider mb-1">
                    기억 강도 및 리스크
                  </div>
                  <div className="grid grid-cols-3 gap-1.5 p-2 rounded bg-apple-card border border-apple-border text-center">
                    <div>
                      <div className="text-[10px] text-apple-secondary">
                        평균 복습 주기
                      </div>
                      <div className="text-xs font-mono font-bold text-apple-text mt-0.5">
                        {deck.avg_interval_months > 0
                          ? `${deck.avg_interval_months}개월`
                          : `${deck.avg_interval_days}일`}
                      </div>
                      <div className="text-[9px] text-apple-secondary font-mono">
                        ({deck.avg_interval_days}일)
                      </div>
                    </div>
                    <div>
                      <div className="text-[10px] text-apple-secondary">
                        평균 Ease
                      </div>
                      <div className="text-xs font-mono font-bold text-apple-text mt-0.5">
                        {deck.avg_ease}%
                      </div>
                      <div className="text-[9px] text-apple-secondary font-mono">
                        (기준 250%)
                      </div>
                    </div>
                    <div>
                      <div className="text-[10px] text-apple-secondary flex items-center justify-center gap-0.5">
                        {deck.deck_leech_count > 0 && (
                          <Flame className="w-2.5 h-2.5 text-apple-red inline" />
                        )}
                        <span>만성 오답</span>
                      </div>
                      <div
                        className={`text-xs font-mono font-bold mt-0.5 ${
                          deck.deck_leech_count > 0
                            ? 'text-apple-red'
                            : 'text-apple-text'
                        }`}
                      >
                        {deck.deck_leech_count.toLocaleString()}
                      </div>
                      <div className="text-[9px] text-apple-secondary font-mono">
                        Lapse≥4회
                      </div>
                    </div>
                  </div>
                </div>

                {/* Section D: Memory Maturity Distribution Gauge */}
                <div className="bg-apple-card p-2.5 rounded-apple-sm border border-apple-border space-y-1.5">
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-apple-secondary text-[10px] font-medium">
                      성숙 카드 비율 (Mature Card Ratio)
                    </span>
                    <span className="font-mono font-bold text-apple-green text-xs">
                      {deck.retention_rate}%
                    </span>
                  </div>

                  {/* Multi-segment stacked progress bar */}
                  <div className="h-1.5 w-full bg-apple-bg rounded-full overflow-hidden flex">
                    <div
                      className="bg-apple-green transition-all"
                      style={{ width: `${maturePct}%` }}
                      title={`성숙 (21일+): ${deck.mature}장 (${maturePct.toFixed(1)}%)`}
                    />
                    <div
                      className="bg-apple-orange transition-all"
                      style={{ width: `${youngPct}%` }}
                      title={`새싹 (1~20일): ${deck.young}장 (${youngPct.toFixed(1)}%)`}
                    />
                    <div
                      className="bg-apple-blue transition-all"
                      style={{ width: `${newPct}%` }}
                      title={`새 카드: ${deck.new_remaining}장 (${newPct.toFixed(1)}%)`}
                    />
                    <div
                      className="bg-apple-secondary/30 transition-all"
                      style={{ width: `${suspendedPct}%` }}
                      title={`보류: ${deck.suspended}장 (${suspendedPct.toFixed(1)}%)`}
                    />
                  </div>

                  {/* Legend Grid */}
                  <div className="grid grid-cols-3 gap-1 text-[10px] text-apple-secondary font-mono pt-1 border-t border-apple-border/50">
                    <div className="flex items-center gap-1">
                      <span className="w-1.5 h-1.5 rounded-full bg-apple-green shrink-0" />
                      <span className="truncate">
                        성숙 {deck.mature.toLocaleString()}
                      </span>
                    </div>
                    <div className="flex items-center gap-1">
                      <span className="w-1.5 h-1.5 rounded-full bg-apple-orange shrink-0" />
                      <span className="truncate">
                        새싹 {deck.young.toLocaleString()}
                      </span>
                    </div>
                    <div className="flex items-center gap-1 justify-end">
                      <span className="w-1.5 h-1.5 rounded-full bg-apple-secondary/50 shrink-0" />
                      <span className="truncate">
                        보류 {deck.suspended.toLocaleString()}
                      </span>
                    </div>
                  </div>
                </div>

                {/* Footer: Cumulative Reps & Review Volume */}
                <div className="pt-2 border-t border-apple-border/60 flex items-center justify-between text-[11px] font-mono text-apple-secondary">
                  <span>누적 복습량</span>
                  <span className="text-apple-text font-semibold">
                    약 {deck.total_reps_est.toLocaleString()} 회
                  </span>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
