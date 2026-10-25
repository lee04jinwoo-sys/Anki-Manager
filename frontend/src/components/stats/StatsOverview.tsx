import React, { useCallback, useEffect, useRef, useState } from 'react'
import { Loader2 } from 'lucide-react'
import { api } from '../../api/client'
import type { StatsOverview as Stats } from '../../types/stats'
import { StatTiles } from './StatTiles'
import { Heatmap } from './Heatmap'
import { ForecastChart } from './ForecastChart'
import { RetentionChart } from './RetentionChart'
import { DeckTable } from './DeckTable'
import { createLatestRequest } from '../../lib/latestRequest'
import { storeForLang, viewForLang, type ByLang, type Lang } from '../../lib/langCache'

/** 학습 통계 영역. refreshKey나 language가 바뀌면 다시 불러온다. */
export const StatsOverview: React.FC<{ refreshKey: number; language?: 'en' | 'zh' }> = ({
  refreshKey,
  language = 'en',
}) => {
  const [cache, setCache] = useState<ByLang<Stats>>({})
  const [loadingLang, setLoadingLang] = useState<Lang | null>(null)
  const [error, setError] = useState<string | null>(null)
  const { data, refreshing } = viewForLang(cache, language, loadingLang)

  const latest = useRef(createLatestRequest())

  const load = useCallback(async () => {
    const isCurrent = latest.current.begin()
    setLoadingLang(language)
    setError(null)
    try {
      const res = await api.getStatsOverview(language)
      if (!isCurrent()) return
      setCache((c) => storeForLang(c, language, res))
    } catch (e) {
      if (!isCurrent()) return
      setError(e instanceof Error ? e.message : '통계를 불러오지 못했습니다.')
    } finally {
      if (isCurrent()) setLoadingLang(null)
    }
  }, [language])

  useEffect(() => {
    load()
  }, [load, refreshKey])

  if (!data) {
    return (
      <div className="flex items-center justify-center gap-2 rounded-apple border border-apple-border bg-apple-card py-16 text-xs text-apple-secondary">
        {error ? error : (<><Loader2 className="h-4 w-4 animate-spin" /> 학습 통계 계산 중...</>)}
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {error && <div className="text-xs text-apple-orange">새로고침 실패: {error} (이전 데이터 표시 중)</div>}
      {refreshing && (
        <div className="flex items-center gap-1.5 text-xs text-apple-secondary">
          <Loader2 className="h-3 w-3 animate-spin" /> 최신 통계 불러오는 중 (지난번 데이터 표시 중)
        </div>
      )}
      <StatTiles data={data} />
      <Heatmap days={data.heatmap} rolloverHour={data.rollover_hour} lang={data.lang} />
      <div className="grid gap-4 lg:grid-cols-2">
        <ForecastChart forecast={data.forecast} language={language} />
        <RetentionChart weeks={data.weekly_retention} target={data.desired_retention} language={language} />
      </div>
      <DeckTable decks={data.decks} target={data.desired_retention} language={language} />
    </div>
  )
}
