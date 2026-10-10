import React, { useState, useEffect, useCallback, useTransition } from 'react'
import {
  Search,
  RotateCcw,
  Sparkles,
  CheckSquare,
  Square,
  Volume2,
  Loader2,
  ChevronLeft,
  ChevronRight,
  Flame,
  Shuffle,
  CheckCircle2,
  AlertCircle,
} from 'lucide-react'
import { api } from '../api/client'
import type {
  LeechAction,
  LinkStats,
  LinkVocabItem,
  LinkVocabResponse,
} from '../types/dashboard'
import type { CorpusAuditStats } from '../types/corpus'
import { PromoteChunkModal } from './modals/PromoteChunkModal'
import { LEECH_ACTIONS, actionLabel, choiceFor, planActions } from '../lib/leechPlan'

interface LinkManagerPanelProps {
  onRefreshDashboard?: () => void
}

type FilterMode = 'leech' | 'zero' | 'low' | 'all'

export const LinkManagerPanel: React.FC<LinkManagerPanelProps> = ({
  onRefreshDashboard,
}) => {
  // Stats state
  const [stats, setStats] = useState<LinkStats | null>(null)
  const [corpusStats, setCorpusStats] = useState<CorpusAuditStats | null>(null)
  const [isScanning, setIsScanning] = useState(false)
  const [scanMessage, setScanMessage] = useState<string | null>(null)

  // Chunk Promotion Modal state
  const [chunkModalItem, setChunkModalItem] = useState<LinkVocabItem | null>(null)
  const [isChunkModalOpen, setIsChunkModalOpen] = useState(false)

  // Vocab table state
  const [vocabData, setVocabData] = useState<LinkVocabResponse>({
    total: 0,
    limit: 25,
    offset: 0,
    items: [],
  })
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Filters (default to 'leech' for high-priority risk resolution)
  const [filterMode, setFilterMode] = useState<FilterMode>('leech')
  const [searchQuery, setSearchQuery] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')
  const [offset, setOffset] = useState(0)
  const limit = 25

  // Selection for Batch Sentence Generation
  const [selectedMap, setSelectedMap] = useState<Map<number, LinkVocabItem>>(
    new Map(),
  )
  const [generateAudio, setGenerateAudio] = useState(true)
  const [isGenerating, setIsGenerating] = useState(false)
  const [generationFeedback, setGenerationFeedback] = useState<string | null>(
    null,
  )

  const [, startTransition] = useTransition()

  // Leech 처리: 단어별 선택(기본값은 서버 추천), 승격 대기열
  const [choices, setChoices] = useState<Map<number, LeechAction>>(new Map())
  const [promoteQueue, setPromoteQueue] = useState<LinkVocabItem[]>([])
  const [isApplying, setIsApplying] = useState(false)

  // Debounce search query
  useEffect(() => {
    const timer = setTimeout(() => {
      startTransition(() => {
        setDebouncedSearch(searchQuery)
        setOffset(0)
      })
    }, 300)
    return () => clearTimeout(timer)
  }, [searchQuery])

  // Load stats
  const fetchStats = useCallback(async () => {
    try {
      const res = await api.getLinkStats()
      setStats(res)
      try {
        const cRes = await api.getCorpusAuditStats()
        setCorpusStats(cRes)
      } catch (ce) {
        console.warn('Corpus stats not loaded:', ce)
      }
    } catch (e) {
      console.error('Failed to load link stats:', e)
    }
  }, [])

  const handleOpenChunkModal = (item: LinkVocabItem) => {
    setChunkModalItem(item)
    setIsChunkModalOpen(true)
  }

  // Load vocab list
  const fetchVocab = useCallback(async () => {
    setIsLoading(true)
    setError(null)
    try {
      const res = await api.getLinkVocab({
        limit,
        offset,
        filter_mode: filterMode,
        search: debouncedSearch || undefined,
      })
      setVocabData(res)
    } catch (e) {
      setError(
        e instanceof Error
          ? e.message
          : '어휘 목록을 불러오는 중 오류가 발생했습니다.',
      )
    } finally {
      setIsLoading(false)
    }
  }, [filterMode, offset, debouncedSearch])

  useEffect(() => {
    fetchStats()
  }, [fetchStats])

  useEffect(() => {
    fetchVocab()
  }, [fetchVocab])

  // Full Scan
  const handleFullScan = async () => {
    setIsScanning(true)
    setScanMessage(null)
    try {
      const res = await api.scanLinks()
      setScanMessage(res.message || '스캔 및 링크 동기화가 완료되었습니다.')
      setTimeout(() => setScanMessage(null), 4000)
      await fetchStats()
      await fetchVocab()
      if (onRefreshDashboard) onRefreshDashboard()
    } catch (e) {
      setError(e instanceof Error ? e.message : '스캔 중 오류가 발생했습니다.')
    } finally {
      setIsScanning(false)
    }
  }

  // Smart Selection: Leech 20
  const handlePickLeech = async () => {
    setIsLoading(true)
    try {
      const res = await api.getLinkLeech(20)
      const nextMap = new Map<number, LinkVocabItem>()
      res.items.forEach((item) => nextMap.set(item.note_id, item))
      setSelectedMap(nextMap)
      setGenerationFeedback(
        `만성 오답 미연결 어휘 ${res.items.length}개가 선택되었습니다.`,
      )
      setTimeout(() => setGenerationFeedback(null), 3500)
    } catch (e) {
      setError(e instanceof Error ? e.message : '오답 단어 추출 실패')
    } finally {
      setIsLoading(false)
    }
  }

  // Smart Selection: Random 20
  const handlePickRandom = async () => {
    setIsLoading(true)
    try {
      const res = await api.getLinkRandom(20)
      const nextMap = new Map<number, LinkVocabItem>()
      res.items.forEach((item) => nextMap.set(item.note_id, item))
      setSelectedMap(nextMap)
      setGenerationFeedback(
        `무작위 미연결 어휘 ${res.items.length}개가 선택되었습니다.`,
      )
      setTimeout(() => setGenerationFeedback(null), 3500)
    } catch (e) {
      setError(e instanceof Error ? e.message : '랜덤 단어 추출 실패')
    } finally {
      setIsLoading(false)
    }
  }

  // Row selection toggle
  const toggleSelectRow = (item: LinkVocabItem) => {
    setSelectedMap((prev) => {
      const next = new Map(prev)
      if (next.has(item.note_id)) {
        next.delete(item.note_id)
      } else {
        next.set(item.note_id, item)
      }
      return next
    })
  }

  // Select all visible rows
  const handleToggleSelectAllVisible = () => {
    const allSelected = vocabData.items.every((it) =>
      selectedMap.has(it.note_id),
    )
    setSelectedMap((prev) => {
      const next = new Map(prev)
      if (allSelected) {
        vocabData.items.forEach((it) => next.delete(it.note_id))
      } else {
        vocabData.items.forEach((it) => next.set(it.note_id, it))
      }
      return next
    })
  }

  // Batch sentence generation
  const handleBatchGenerate = async () => {
    if (selectedMap.size === 0) return
    setIsGenerating(true)
    setGenerationFeedback(null)
    setError(null)
    try {
      const wordsPayload = Array.from(selectedMap.values()).map((v) => ({
        note_id: v.note_id,
        word: v.word,
        meaning: v.meaning,
      }))
      const res = await api.batchGenerateSentences(wordsPayload, generateAudio)
      setGenerationFeedback(
        `AI 실생활 예문 ${res.created_count ?? selectedMap.size}개가 생성되어 Sentence 덱에 자동 추가되었습니다!`,
      )
      setSelectedMap(new Map())
      await fetchStats()
      await fetchVocab()
      if (onRefreshDashboard) onRefreshDashboard()
    } catch (e) {
      setError(
        e instanceof Error
          ? e.message
          : 'AI 예문 일괄 생성 중 오류가 발생했습니다.',
      )
    } finally {
      setIsGenerating(false)
    }
  }

  const setChoice = (noteId: number, action: LeechAction) =>
    setChoices((prev) => new Map(prev).set(noteId, action))

  // 승격 대기열: 창이 닫힐 때마다 다음 단어를 연다
  useEffect(() => {
    if (promoteQueue.length > 0 && !isChunkModalOpen) {
      setChunkModalItem(promoteQueue[0]!)
      setIsChunkModalOpen(true)
    }
  }, [promoteQueue, isChunkModalOpen])

  const closeChunkModal = () => {
    setIsChunkModalOpen(false)
    setPromoteQueue((q) => (q.length > 0 && q[0]!.note_id === chunkModalItem?.note_id ? q.slice(1) : q))
  }

  const waitForJobThenRefresh = async () => {
    const deadline = Date.now() + 10 * 60 * 1000
    while (Date.now() < deadline) {
      await new Promise((r) => setTimeout(r, 1500))
      try {
        const st = await api.getJobState()
        if (!st.is_running) break
      } catch {
        break
      }
    }
    await fetchStats()
    await fetchVocab()
    if (onRefreshDashboard) onRefreshDashboard()
  }

  const handleApplyLeech = async () => {
    const plan = planActions(Array.from(selectedMap.values()), choices)
    const c = plan.counts
    const lines = [
      `다시 학습 ${c.review_today} · 예문 추가 ${c.examples} · 청크 승격 ${c.promote} · 초기화 ${c.reset} · 건너뛰기 ${c.skip}`,
      c.reset > 0 ? '⚠ 초기화한 카드는 학습 기록이 끊깁니다 (실행 전 상태는 data/backups/leech/ 에 저장).' : '',
      c.promote > 0 ? '청크 승격은 적용 후 단어마다 후보를 보고 직접 고릅니다.' : '',
      '진행할까요?',
    ].filter(Boolean)
    if (!window.confirm(lines.join('\n'))) return

    setIsApplying(true)
    setError(null)
    try {
      if (plan.batch.length > 0) {
        const res = await api.applyLeechActions(plan.batch)
        if (res.status !== 'success') {
          setError(res.message || 'Leech 처리를 시작하지 못했습니다.')
          return
        }
        setGenerationFeedback('Leech 처리 작업을 시작했습니다. 진행 상황은 오른쪽 아래 작업 창에서 볼 수 있습니다.')
        void waitForJobThenRefresh()
      }
      setSelectedMap(new Map())
      setChoices(new Map())
      if (plan.promoteQueue.length > 0) setPromoteQueue(plan.promoteQueue)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Leech 처리 요청 실패')
    } finally {
      setIsApplying(false)
    }
  }

  const isLeechMode = filterMode === 'leech'
  const leechPlan = isLeechMode ? planActions(Array.from(selectedMap.values()), choices) : null

  const totalPages = Math.ceil(vocabData.total / limit) || 1
  const currentPage = Math.floor(offset / limit) + 1
  const selectedCount = selectedMap.size

  const coveragePercent =
    stats && stats.total_vocab > 0
      ? (
          ((stats.total_vocab - stats.unlinked_vocab) / stats.total_vocab) *
          100
        ).toFixed(1)
      : '0.0'

  return (
    <div className="bg-apple-card border border-apple-border rounded-apple p-5 shadow-apple-card space-y-4.5">
      {/* 1. Header */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h2 className="text-sm font-semibold text-apple-text">단어 문맥 · 만성 오답</h2>
          <p className="text-xs text-apple-secondary">
            단어가 실제 문장 카드에 얼마나 등장하는지와 자꾸 틀리는 단어를 보고, AI 예문 생성이나 청크 승격으로 처방합니다
          </p>
        </div>
        <div className="flex items-center gap-2">
          {scanMessage && (
            <span className="flex items-center gap-1 text-xs text-apple-secondary">
              <CheckCircle2 className="h-3.5 w-3.5 text-apple-green" />
              {scanMessage}
            </span>
          )}
          <button
            type="button"
            onClick={handleFullScan}
            disabled={isScanning}
            className="inline-flex items-center gap-1.5 rounded-apple-sm border border-apple-border bg-apple-subtle px-3 py-1.5 text-xs font-medium text-apple-text hover:border-apple-borderStrong hover:bg-apple-subtleHover disabled:opacity-40"
            title="Anki의 모든 단어·문장을 다시 읽어 연결을 새로 계산"
          >
            <RotateCcw className={`h-3.5 w-3.5 text-apple-secondary ${isScanning ? 'animate-spin text-apple-blue' : ''}`} />
            {isScanning ? '재스캔 중...' : '연결 재스캔'}
          </button>
        </div>
      </div>

      {/* 2. Key numbers */}
      {stats && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {[
            { label: '등록 단어', value: stats.total_vocab.toLocaleString(), unit: '개', sub: `문장 연결 ${stats.total_links.toLocaleString()}건` },
            { label: '문장에 등장하는 단어', value: coveragePercent, unit: '%', sub: '1개 이상의 문장 카드에 등장', meter: Number(coveragePercent) },
            { label: '문장이 하나도 없는 단어', value: stats.unlinked_vocab.toLocaleString(), unit: '개', sub: '예문 생성 대상' },
            { label: '만성 오답 단어', value: (stats.leech_count ?? 0).toLocaleString(), unit: '개', sub: 'Lapse 4회+ 또는 Ease 130% 이하' },
          ].map((t) => (
            <div key={t.label} className="rounded-apple-sm border border-apple-border bg-apple-subtle/60 p-3">
              <div className="text-[11px] text-apple-secondary">{t.label}</div>
              <div className="mt-0.5 text-lg font-semibold text-apple-text">
                {t.value}
                <span className="ml-0.5 text-xs font-normal text-apple-secondary">{t.unit}</span>
              </div>
              {t.meter !== undefined && (
                <div className="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-[var(--viz-empty)]">
                  <div className="h-full rounded-full bg-[var(--viz-seq-3)]" style={{ width: `${Math.min(100, t.meter)}%` }} />
                </div>
              )}
              <div className="mt-1 text-[11px] text-apple-secondary">{t.sub}</div>
            </div>
          ))}
        </div>
      )}

      {/* 2.5 Corpus frequency tiers (one stacked bar) */}
      {corpusStats && corpusStats.total_notes > 0 && (() => {
        const tiers: [string, string, string][] = [["freq::tier1_essential","필수 (~3천위)","var(--viz-seq-4)"],["freq::tier2_common","상용 (~1만위)","var(--viz-seq-3)"],["freq::tier3_advanced","고급 (~2.5만위)","var(--viz-seq-2)"],["freq::tier4_academic","학술 (~6만위)","var(--viz-seq-1)"],["freq::tier5_rare","희귀","var(--viz-neutral)"]]
        const total = tiers.reduce((acc, [k]) => acc + (corpusStats.tier_distribution[k] ?? 0), 0) || 1
        return (
          <div className="rounded-apple-sm border border-apple-border p-3">
            <div className="mb-2 flex flex-wrap items-baseline justify-between gap-2">
              <span className="text-xs font-medium text-apple-text">단어 빈도 등급 (영어 코퍼스 순위 기준)</span>
              <span className="text-[11px] text-apple-secondary">
                {corpusStats.total_notes.toLocaleString()}개 단어{corpusStats.generated_at ? ` · ${corpusStats.generated_at} 기준` : ''}
              </span>
            </div>
            <div className="flex h-2.5 w-full gap-[2px] overflow-hidden rounded-full">
              {tiers.map(([k, label, color]) => {
                const v = corpusStats.tier_distribution[k] ?? 0
                return v > 0 ? (
                  <div key={k} title={`${label}: ${v.toLocaleString()}개 (${((v / total) * 100).toFixed(1)}%)`} style={{ width: `${(v / total) * 100}%`, background: color }} />
                ) : null
              })}
            </div>
            <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-apple-secondary">
              {tiers.map(([k, label, color]) => (
                <span key={k} className="inline-flex items-center gap-1.5">
                  <span className="inline-block h-2 w-2 rounded-full" style={{ background: color }} />
                  {label} <span className="font-mono text-apple-text">{(corpusStats.tier_distribution[k] ?? 0).toLocaleString()}</span>
                </span>
              ))}
            </div>
          </div>
        )
      })()}

      {/* 3. Controls & Filter Bar */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 pt-1">
        {/* Search & Filter Chips */}
        <div className="flex flex-wrap items-center gap-2">
          {/* Search Input */}
          <div className="relative min-w-[220px]">
            <Search className="w-3.5 h-3.5 text-apple-secondary absolute left-2.5 top-1/2 -translate-y-1/2 pointer-events-none" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="단어 또는 뜻 검색..."
              className="w-full pl-8 pr-3 py-1.5 text-xs bg-apple-bg border border-apple-border focus:border-apple-blue rounded-apple-sm text-apple-text placeholder-apple-secondary outline-none transition-colors"
            />
          </div>

          {/* Unified Filter Mode Toggle */}
          <div className="inline-flex rounded-apple-sm bg-apple-bg border border-apple-border p-0.5 text-xs">
            <button
              type="button"
              onClick={() => {
                setFilterMode('leech')
                setOffset(0)
              }}
              className={`px-2.5 py-1 rounded transition-colors flex items-center gap-1 ${
                filterMode === 'leech'
                  ? 'bg-apple-red/20 text-apple-red font-semibold shadow-apple-subtle'
                  : 'text-apple-secondary hover:text-apple-text'
              }`}
            >
              <Flame className="w-3 h-3" />
              <span>망각 위험군 (Leech)</span>
            </button>
            <button
              type="button"
              onClick={() => {
                setFilterMode('zero')
                setOffset(0)
              }}
              className={`px-2.5 py-1 rounded transition-colors ${
                filterMode === 'zero'
                  ? 'bg-apple-card font-semibold text-apple-text shadow-apple-subtle'
                  : 'text-apple-secondary hover:text-apple-text'
              }`}
            >
              미연결 (0개)
            </button>
            <button
              type="button"
              onClick={() => {
                setFilterMode('low')
                setOffset(0)
              }}
              className={`px-2.5 py-1 rounded transition-colors ${
                filterMode === 'low'
                  ? 'bg-apple-card font-semibold text-apple-text shadow-apple-subtle'
                  : 'text-apple-secondary hover:text-apple-text'
              }`}
            >
              문맥 부족 (1개 이하)
            </button>
            <button
              type="button"
              onClick={() => {
                setFilterMode('all')
                setOffset(0)
              }}
              className={`px-2.5 py-1 rounded transition-colors ${
                filterMode === 'all'
                  ? 'bg-apple-card font-semibold text-apple-text shadow-apple-subtle'
                  : 'text-apple-secondary hover:text-apple-text'
              }`}
            >
              전체
            </button>
          </div>
        </div>

        {/* Smart Pick Buttons */}
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={handlePickLeech}
            className="inline-flex items-center gap-1.5 px-2.5 py-1.5 text-xs font-medium text-apple-red bg-apple-red/10 hover:bg-apple-red/15 rounded-apple-sm border border-apple-red/20 transition-all shadow-apple-subtle"
            title="많이 틀리는 미연결 단어 20개 자동 선택"
          >
            <Flame className="w-3.5 h-3.5" />
            <span>오답 20개 추출</span>
          </button>
          <button
            type="button"
            onClick={handlePickRandom}
            className="inline-flex items-center gap-1.5 px-2.5 py-1.5 text-xs font-medium text-apple-text bg-apple-subtle hover:bg-apple-subtleHover rounded-apple-sm border border-apple-border hover:border-apple-borderStrong transition-all shadow-apple-subtle"
            title="무작위 미연결 단어 20개 자동 선택"
          >
            <Shuffle className="w-3.5 h-3.5 text-apple-secondary" />
            <span>랜덤 20개</span>
          </button>
          {selectedCount > 0 && (
            <button
              type="button"
              onClick={() => setSelectedMap(new Map())}
              className="px-2.5 py-1.5 text-xs text-apple-secondary hover:text-apple-text transition-colors"
            >
              선택 해제 ({selectedCount})
            </button>
          )}
        </div>
      </div>

      {/* Messages */}
      {error && (
        <div className="p-3 rounded-apple-sm bg-apple-red/10 border border-apple-red/20 text-xs text-apple-red flex items-center gap-2">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {generationFeedback && (
        <div className="p-3 rounded-apple-sm bg-apple-green/10 border border-apple-green/20 text-xs text-apple-green flex items-center gap-2 animate-fade-in">
          <CheckCircle2 className="w-4 h-4 shrink-0" />
          <span>{generationFeedback}</span>
        </div>
      )}

      {/* 4. Unified Data Table */}
      <div className="border border-apple-border rounded-apple-sm overflow-hidden bg-apple-card">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse text-xs">
            <thead>
              <tr className="border-b border-apple-border bg-apple-subtle/50 text-apple-secondary font-medium">
                <th className="py-2.5 px-3 w-10 text-center">
                  <button
                    type="button"
                    onClick={handleToggleSelectAllVisible}
                    className="p-0.5 hover:text-apple-text transition-colors"
                    title="현재 페이지 전체 선택/해제"
                  >
                    {vocabData.items.length > 0 &&
                    vocabData.items.every((it) =>
                      selectedMap.has(it.note_id),
                    ) ? (
                      <CheckSquare className="w-4 h-4 text-apple-blue" />
                    ) : (
                      <Square className="w-4 h-4" />
                    )}
                  </button>
                </th>
                <th className="py-2.5 px-3 min-w-[140px]">단어 / 숙어</th>
                <th className="py-2.5 px-2 w-16 text-center">품사</th>
                <th className="py-2.5 px-3 min-w-[180px]">뜻 / 의미</th>
                <th className="py-2.5 px-2 w-20 text-center">오답 (Lapse)</th>
                <th className="py-2.5 px-2 w-20 text-center">난이도 (Ease)</th>
                <th className="py-2.5 px-3 w-24 text-center">문장 연결</th>
                {isLeechMode ? (
                  <th className="py-2.5 px-3 min-w-[200px]">처리 (기본값은 추천)</th>
                ) : (
                  <>
                    <th className="py-2.5 px-3 w-24 text-center">리스크 진단</th>
                    <th className="py-2.5 px-3 w-24 text-center">청크 승격</th>
                  </>
                )}
              </tr>
            </thead>
            <tbody className="divide-y divide-apple-border/60">
              {isLoading ? (
                <tr>
                  <td colSpan={9} className="py-12 text-center text-apple-secondary">
                    <Loader2 className="w-5 h-5 animate-spin mx-auto text-apple-blue mb-2" />
                    <span>어휘 목록 로딩 중...</span>
                  </td>
                </tr>
              ) : vocabData.items.length === 0 ? (
                <tr>
                  <td
                    colSpan={9}
                    className="py-12 text-center text-apple-secondary"
                  >
                    해당 조건에 해당하는 어휘가 없습니다.
                  </td>
                </tr>
              ) : (
                vocabData.items.map((item) => {
                  const isChecked = selectedMap.has(item.note_id)
                  const isZero = item.link_count === 0
                  const isLeech =
                    (item.lapses !== undefined && item.lapses >= 4) ||
                    (item.ease !== undefined && item.ease <= 130 && item.ease > 0)

                  return (
                    <tr
                      key={item.note_id}
                      onClick={() => toggleSelectRow(item)}
                      className={`cursor-pointer transition-colors ${
                        isChecked
                          ? 'bg-apple-blue/10 hover:bg-apple-blue/15'
                          : 'hover:bg-apple-subtle/40'
                      }`}
                    >
                      <td
                        className="py-2.5 px-3 text-center"
                        onClick={(e) => e.stopPropagation()}
                      >
                        <button
                          type="button"
                          onClick={() => toggleSelectRow(item)}
                          className="p-0.5 text-apple-secondary hover:text-apple-text transition-colors"
                        >
                          {isChecked ? (
                            <CheckSquare className="w-4 h-4 text-apple-blue" />
                          ) : (
                            <Square className="w-4 h-4" />
                          )}
                        </button>
                      </td>
                      <td className="py-2.5 px-3 font-mono font-semibold text-apple-text">
                        {item.word}
                      </td>
                      <td className="py-2.5 px-2 text-center">
                        <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-apple-bg text-apple-secondary border border-apple-border">
                          {item.pos || '미분류'}
                        </span>
                      </td>
                      <td className="py-2.5 px-3 text-apple-secondary truncate max-w-xs">
                        {item.meaning}
                      </td>
                      <td className="py-2.5 px-2 text-center font-mono">
                        {item.lapses !== undefined && item.lapses > 0 ? (
                          <span
                            className={
                              item.lapses >= 4
                                ? 'font-bold text-apple-red'
                                : 'text-apple-text'
                            }
                          >
                            {item.lapses}회
                          </span>
                        ) : (
                          <span className="text-apple-secondary text-[11px]">-</span>
                        )}
                      </td>
                      <td className="py-2.5 px-2 text-center font-mono">
                        {item.ease !== undefined && item.ease > 0 ? (
                          <span
                            className={
                              item.ease <= 130
                                ? 'font-bold text-apple-red'
                                : 'text-apple-text'
                            }
                          >
                            {item.ease}%
                          </span>
                        ) : (
                          <span className="text-apple-secondary text-[11px]">-</span>
                        )}
                      </td>
                      <td className="py-2.5 px-3 text-center font-mono">
                        <span
                          className={`inline-block px-2 py-0.5 rounded text-[11px] font-medium border ${
                            isZero
                              ? 'bg-apple-orange/10 text-apple-orange border-apple-orange/30'
                              : 'bg-apple-green/10 text-apple-green border-apple-green/30'
                          }`}
                        >
                          {item.link_count}개
                        </span>
                      </td>
                      {isLeechMode ? (
                        <td className="py-2 px-3" onClick={(e) => e.stopPropagation()}>
                          <select
                            value={choiceFor(item, choices)}
                            onChange={(e) => setChoice(item.note_id, e.target.value as LeechAction)}
                            className="w-full rounded-apple-sm border border-apple-border bg-apple-bg px-2 py-1 text-xs text-apple-text outline-none focus:border-apple-blue"
                            title={LEECH_ACTIONS.find((a) => a.value === choiceFor(item, choices))?.hint}
                          >
                            {LEECH_ACTIONS.map((a) => (
                              <option key={a.value} value={a.value}>
                                {a.label}
                                {item.suggestion?.action === a.value ? ' (추천)' : ''}
                              </option>
                            ))}
                          </select>
                          {item.suggestion && (
                            <div className="mt-1 text-[10px] leading-snug text-apple-secondary">{item.suggestion.reason}</div>
                          )}
                        </td>
                      ) : (
                        <>
                        <td className="py-2.5 px-3 text-center">
                          {isLeech && isZero ? (
                            <span className="text-[10px] font-medium text-apple-red bg-apple-red/10 px-2 py-0.5 rounded border border-apple-red/20">
                              고위험 고립
                            </span>
                          ) : isZero ? (
                            <span className="text-[10px] text-apple-orange font-medium bg-apple-orange/10 px-2 py-0.5 rounded border border-apple-orange/20">
                              미연결
                            </span>
                          ) : isLeech ? (
                            <span className="text-[10px] text-purple-400 font-medium bg-purple-500/10 px-2 py-0.5 rounded border border-purple-500/20">
                              반복 망각
                            </span>
                          ) : (
                            <span className="text-[10px] text-apple-secondary font-mono">
                              안정
                            </span>
                          )}
                        </td>
                        <td
                          className="py-2.5 px-3 text-center"
                          onClick={(e) => e.stopPropagation()}
                        >
                          <button
                            type="button"
                            onClick={() => handleOpenChunkModal(item)}
                            className="inline-flex items-center gap-1 px-2 py-1 text-[11px] font-medium text-amber-300 bg-amber-500/10 hover:bg-amber-500/20 border border-amber-500/30 rounded-md transition-colors shadow-sm"
                            title="고빈도 청크로 1-클릭 승격"
                          >
                            <Sparkles className="w-3 h-3 text-amber-400" />
                            <span>청크 승격</span>
                          </button>
                        </td>
                        </>
                      )}
                    </tr>
                  )
                })
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination Bar */}
        <div className="p-3 border-t border-apple-border/80 flex items-center justify-between text-xs text-apple-secondary font-mono bg-apple-subtle/20">
          <div>
            총 {vocabData.total.toLocaleString()}개 중{' '}
            {vocabData.items.length > 0 ? offset + 1 : 0} ~{' '}
            {Math.min(offset + limit, vocabData.total)}
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              disabled={offset === 0 || isLoading}
              onClick={() => setOffset(Math.max(0, offset - limit))}
              className="p-1 rounded bg-apple-bg hover:bg-apple-subtle text-apple-text border border-apple-border disabled:opacity-30 disabled:pointer-events-none transition-colors"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
            <span className="text-apple-text font-semibold px-1">
              {currentPage} / {totalPages}
            </span>
            <button
              type="button"
              disabled={offset + limit >= vocabData.total || isLoading}
              onClick={() => setOffset(offset + limit)}
              className="p-1 rounded bg-apple-bg hover:bg-apple-subtle text-apple-text border border-apple-border disabled:opacity-30 disabled:pointer-events-none transition-colors"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>

      {/* 5a. Leech 처리 적용 바 */}
      {isLeechMode && selectedCount > 0 && leechPlan && (
        <div className="flex flex-col justify-between gap-3 rounded-apple-sm border border-apple-blue/40 bg-apple-card p-3.5 shadow-apple-card sm:flex-row sm:items-center">
          <div className="flex flex-wrap items-center gap-2 text-xs">
            <span className="rounded bg-apple-blue/20 px-2 py-1 font-mono font-bold text-apple-blue">{selectedCount}개 선택</span>
            {(['review_today', 'examples', 'promote', 'reset', 'skip'] as LeechAction[])
              .filter((a) => leechPlan.counts[a] > 0)
              .map((a) => (
                <span key={a} className="rounded border border-apple-border px-2 py-0.5 text-apple-secondary">
                  {actionLabel(a)} <span className="font-mono text-apple-text">{leechPlan.counts[a]}</span>
                </span>
              ))}
          </div>
          <button
            type="button"
            onClick={handleApplyLeech}
            disabled={isApplying || leechPlan.batch.length + leechPlan.promoteQueue.length === 0}
            className="inline-flex items-center gap-1.5 rounded-apple-sm bg-apple-blue px-4 py-2 text-xs font-semibold text-white hover:bg-apple-blueHover disabled:opacity-50"
          >
            {isApplying ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <CheckCircle2 className="h-3.5 w-3.5" />}
            선택한 처리 적용
          </button>
        </div>
      )}

      {/* 5b. Sticky Action Bar for Batch Sentence Generation */}
      {!isLeechMode && selectedCount > 0 && (
        <div className="p-3.5 rounded-apple-sm bg-apple-card border border-apple-blue/40 shadow-apple-card flex flex-col sm:flex-row sm:items-center justify-between gap-3 animate-fade-in">
          <div className="flex items-center gap-3">
            <div className="px-2 py-1 rounded bg-apple-blue/20 text-apple-blue font-mono font-bold text-xs">
              {selectedCount}개 선택됨
            </div>
            <label className="flex items-center gap-1.5 text-xs text-apple-secondary cursor-pointer hover:text-apple-text transition-colors">
              <input
                type="checkbox"
                checked={generateAudio}
                onChange={(e) => setGenerateAudio(e.target.checked)}
                className="rounded border-apple-border text-apple-blue focus:ring-0"
              />
              <Volume2 className="w-3.5 h-3.5 text-apple-secondary" />
              <span>TTS 오디오 동시 생성 (Chirp3-HD / gTTS)</span>
            </label>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={handleBatchGenerate}
              disabled={isGenerating}
              className="inline-flex items-center gap-1.5 px-4 py-2 text-xs font-semibold text-white bg-apple-blue hover:bg-apple-blueHover rounded-apple-sm transition-all shadow-apple-subtle disabled:opacity-50"
            >
              {isGenerating ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
              ) : (
                <Sparkles className="w-3.5 h-3.5 text-white" />
              )}
              <span>
                {isGenerating
                  ? 'Gemini 예문 및 TTS 생성 중...'
                  : `Gemini AI 예문 일괄 생성 (${selectedCount}개)`}
              </span>
            </button>
          </div>
        </div>
      )}

      {/* 6. Promote Chunk Modal */}
      <PromoteChunkModal
        isOpen={isChunkModalOpen}
        onClose={closeChunkModal}
        targetItem={chunkModalItem}
        onPromoted={() => {
          fetchVocab()
          fetchStats()
          if (onRefreshDashboard) onRefreshDashboard()
        }}
      />
    </div>
  )
}
