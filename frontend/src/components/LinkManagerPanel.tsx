import React, { useState, useEffect, useCallback, useRef, useTransition } from 'react'
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
import { PromoteReviewModal } from './modals/PromoteReviewModal'
import { LEECH_ACTIONS, actionLabel, choiceFor, planActions } from '../lib/leechPlan'
import { createLatestRequest } from '../lib/latestRequest'

const TIER_LABELS: Record<string, string> = {
  'freq::tier1_essential': '필수',
  'freq::tier2_common': '상용',
  'freq::tier3_advanced': '고급',
  'freq::tier4_academic': '학술',
  'freq::tier5_rare': '희귀',
}
const tierLabel = (t?: string) => (t ? TIER_LABELS[t] ?? '–' : '–')

interface LinkManagerPanelProps {
  onRefreshDashboard?: () => void
  language?: 'en' | 'zh'
}

type FilterMode = 'leech' | 'treated' | 'zero' | 'low' | 'all'

const RELAPSE_LAPSES = 4 // backend/services/leech_history.py 와 같은 값
const dateOf = (ts: number) => {
  const d = new Date(ts * 1000)
  return `${d.getMonth() + 1}/${d.getDate()}`
}

export const LinkManagerPanel: React.FC<LinkManagerPanelProps> = ({
  onRefreshDashboard,
  language = 'en',
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

  // Filters (default to 'all' if Chinese since leech is mostly 0, else 'leech')
  const [filterMode, setFilterMode] = useState<FilterMode>(language === 'zh' ? 'all' : 'leech')
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

  // Reset selection and mode on language switch
  useEffect(() => {
    setStats(null)
    setCorpusStats(null)
    setSelectedMap(new Map())
    setOffset(0)
    setFilterMode(language === 'zh' ? 'all' : 'leech')
  }, [language])

  const [, startTransition] = useTransition()

  // Leech 처리: 단어별 선택(기본값은 서버 추천), 승격 대기열
  const [choices, setChoices] = useState<Map<number, LeechAction>>(new Map())
  const [reviewItems, setReviewItems] = useState<LinkVocabItem[]>([])
  const [isReviewOpen, setIsReviewOpen] = useState(false)
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

  const latestStats = useRef(createLatestRequest())
  const latestVocab = useRef(createLatestRequest())

  // Load stats
  const fetchStats = useCallback(async () => {
    const isCurrent = latestStats.current.begin()
    try {
      const res = await api.getLinkStats(language)
      if (!isCurrent()) return
      setStats(res)
      if (language === 'en') {
        try {
          const cRes = await api.getCorpusAuditStats()
          if (!isCurrent()) return
          setCorpusStats(cRes)
        } catch (ce) {
          console.warn('Corpus stats not loaded:', ce)
        }
      } else {
        setCorpusStats(null)
      }
    } catch (e) {
      console.error('Failed to load link stats:', e)
    }
  }, [language])

  const handleOpenChunkModal = (item: LinkVocabItem) => {
    setChunkModalItem(item)
    setIsChunkModalOpen(true)
  }

  // Load vocab list
  const fetchVocab = useCallback(async () => {
    const isCurrent = latestVocab.current.begin()
    setIsLoading(true)
    setError(null)
    try {
      const res = await api.getLinkVocab({
        limit,
        offset,
        filter_mode: filterMode,
        search: debouncedSearch || undefined,
        lang: language,
      })
      if (!isCurrent()) return
      setVocabData(res)
    } catch (e) {
      if (!isCurrent()) return
      setError(
        e instanceof Error
          ? e.message
          : '어휘 목록을 불러오는 중 오류가 발생했습니다.',
      )
    } finally {
      if (isCurrent()) setIsLoading(false)
    }
  }, [filterMode, offset, debouncedSearch, language])

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
      const res = await api.scanLinks(language)
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
      const res = await api.getLinkLeech(20, language)
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
      const res = await api.getLinkRandom(20, language)
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
      const res = await api.batchGenerateSentences(wordsPayload, generateAudio, language)
      setGenerationFeedback(
        `AI 실생활 예문 ${res.created_count ?? selectedMap.size}개가 생성되어 ${language === 'zh' ? 'Chinese Sentence' : 'English Sentence'} 덱에 자동 추가되었습니다!`,
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
      c.promote > 0 ? '청크 승격은 다음 화면에서 단어별 후보를 한 번에 보고 고릅니다.' : '',
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
      if (plan.promoteQueue.length > 0) {
        setReviewItems(plan.promoteQueue)
        setIsReviewOpen(true)
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Leech 처리 요청 실패')
    } finally {
      setIsApplying(false)
    }
  }

  const isLeechMode = filterMode === 'leech'
  const isTreatedMode = filterMode === 'treated'
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
            { label: '만성 오답 단어', value: (stats.leech_count ?? 0).toLocaleString(), unit: '개', sub: '필수·상용·고급 중 오답 4회+ 또는 Ease 130% 이하' },
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
              className={`px-2.5 py-1 rounded transition-colors ${
                filterMode === 'leech'
                  ? 'bg-apple-card font-semibold text-apple-text shadow-apple-subtle'
                  : 'text-apple-secondary hover:text-apple-text'
              }`}
            >
              만성 오답
            </button>
            <button
              type="button"
              onClick={() => {
                setFilterMode('treated')
                setOffset(0)
              }}
              className={`px-2.5 py-1 rounded transition-colors ${
                filterMode === 'treated'
                  ? 'bg-apple-card font-semibold text-apple-text shadow-apple-subtle'
                  : 'text-apple-secondary hover:text-apple-text'
              }`}
              title="처리한 단어와 처리 후 경과. 처리 후 4회 더 틀리면 만성 오답 목록으로 돌아갑니다"
            >
              처리됨
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
            className="inline-flex items-center gap-1.5 rounded-apple-sm border border-apple-border bg-apple-subtle px-2.5 py-1.5 text-xs font-medium text-apple-text hover:bg-apple-subtleHover"
            title="문장이 하나도 없는 단어 중 가장 많이 틀린 20개 선택"
          >
            <Flame className="h-3.5 w-3.5 text-apple-secondary" />
            <span>오답 많은 20개 선택</span>
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

      {/* 4. 단어 표 */}
      <div className="overflow-hidden rounded-apple-sm border border-apple-border">
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-left text-xs">
            <thead>
              <tr className="border-b border-apple-border text-[11px] text-apple-secondary">
                <th className="w-10 px-3 py-2 text-center font-normal">
                  <button
                    type="button"
                    onClick={handleToggleSelectAllVisible}
                    className="p-0.5 hover:text-apple-text"
                    title="이 페이지 전체 선택/해제"
                  >
                    {vocabData.items.length > 0 && vocabData.items.every((it) => selectedMap.has(it.note_id)) ? (
                      <CheckSquare className="h-4 w-4 text-apple-blue" />
                    ) : (
                      <Square className="h-4 w-4" />
                    )}
                  </button>
                </th>
                <th className="px-3 py-2 font-normal">단어</th>
                <th className="w-16 px-2 py-2 text-right font-normal">오답</th>
                <th className="w-16 px-2 py-2 text-right font-normal">문장</th>
                {isLeechMode && <th className="w-20 px-2 py-2 font-normal">빈도</th>}
                <th className={`px-3 py-2 font-normal ${isLeechMode ? 'w-[260px]' : isTreatedMode ? 'w-[220px]' : 'w-28 text-right'}`}>
                  {isLeechMode ? '처리' : isTreatedMode ? '처리 · 처리 후 오답' : ''}
                </th>
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                <tr>
                  <td colSpan={6} className="py-12 text-center text-apple-secondary">
                    <Loader2 className="mx-auto mb-2 h-5 w-5 animate-spin text-apple-blue" />
                    어휘 목록 로딩 중...
                  </td>
                </tr>
              ) : vocabData.items.length === 0 ? (
                <tr>
                  <td colSpan={6} className="py-12 text-center text-apple-secondary">
                    해당 조건에 맞는 단어가 없습니다.
                  </td>
                </tr>
              ) : (
                vocabData.items.map((item) => {
                  const isChecked = selectedMap.has(item.note_id)
                  const choice = choiceFor(item, choices)
                  return (
                    <tr
                      key={item.note_id}
                      onClick={() => toggleSelectRow(item)}
                      className={`cursor-pointer border-t border-apple-border/60 ${isChecked ? 'bg-apple-blue/10' : 'hover:bg-apple-subtle/40'}`}
                    >
                      <td className="px-3 py-2 text-center text-apple-secondary">
                        {isChecked ? <CheckSquare className="mx-auto h-4 w-4 text-apple-blue" /> : <Square className="mx-auto h-4 w-4" />}
                      </td>
                      <td className="max-w-0 px-3 py-2">
                        <div className="truncate text-[13px] font-medium text-apple-text">
                          {item.word}
                          {isLeechMode && item.treated?.relapsed && (
                            <span className="ml-2 text-[10px] font-normal text-apple-orange" title={`${dateOf(item.treated.treated_at)} ${actionLabel(item.treated.action)} 후 ${item.treated.lapses_since}회 오답`}>
                              재발 · 처리 후 {item.treated.lapses_since}회 오답
                            </span>
                          )}
                        </div>
                        <div className="truncate text-[11px] text-apple-secondary">
                          {item.pos && <span className="mr-1.5 opacity-70">{item.pos}</span>}
                          {item.meaning}
                        </div>
                      </td>
                      <td className="px-2 py-2 text-right font-mono text-apple-text">
                        {item.lapses ? item.lapses : <span className="text-apple-secondary">–</span>}
                      </td>
                      <td className="px-2 py-2 text-right font-mono">
                        {item.link_count > 0 ? <span className="text-apple-text">{item.link_count}</span> : <span className="text-apple-secondary">0</span>}
                      </td>
                      {isLeechMode && (
                        <td className="px-2 py-2 text-[11px] text-apple-secondary">{tierLabel(item.tier)}</td>
                      )}
                      {isLeechMode ? (
                        <td className="px-3 py-1.5" onClick={(e) => e.stopPropagation()}>
                          <select
                            value={choice}
                            onChange={(e) => setChoice(item.note_id, e.target.value as LeechAction)}
                            className="w-full rounded-apple-sm border border-apple-border bg-apple-bg px-2 py-1 text-xs text-apple-text outline-none focus:border-apple-blue"
                          >
                            {LEECH_ACTIONS.map((a) => (
                              <option key={a.value} value={a.value}>
                                {a.label}
                                {item.suggestion?.action === a.value ? ' · 추천' : ''}
                              </option>
                            ))}
                          </select>
                          {item.suggestion && (
                            <div className="mt-0.5 truncate text-[10px] text-apple-secondary" title={item.suggestion.reason}>
                              {item.suggestion.reason}
                            </div>
                          )}
                        </td>
                      ) : isTreatedMode && item.treated ? (
                        <td className="px-3 py-2">
                          <div className="text-xs text-apple-text">
                            {actionLabel(item.treated.action)} <span className="text-apple-secondary">· {dateOf(item.treated.treated_at)}</span>
                          </div>
                          <div className={`text-[11px] ${item.treated.relapsed ? 'text-apple-orange' : 'text-apple-secondary'}`}>
                            처리 후 오답 {item.treated.lapses_since}/{RELAPSE_LAPSES}회{item.treated.relapsed ? ' · 재발' : ''}
                          </div>
                        </td>
                      ) : (
                        <td className="px-3 py-2 text-right" onClick={(e) => e.stopPropagation()}>
                          <button
                            type="button"
                            onClick={() => handleOpenChunkModal(item)}
                            className="text-[11px] text-apple-secondary underline-offset-2 hover:text-apple-text hover:underline"
                            title="고빈도 청크로 바꾸기"
                          >
                            청크 승격
                          </button>
                        </td>
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

      {/* 6a. 청크 승격 한 화면 검토 */}
      <PromoteReviewModal
        isOpen={isReviewOpen}
        items={reviewItems}
        onClose={() => setIsReviewOpen(false)}
        onStarted={() => {
          setGenerationFeedback('청크 승격 작업을 시작했습니다. 진행 상황은 오른쪽 아래 작업 창에서 볼 수 있습니다.')
          void waitForJobThenRefresh()
        }}
      />

      {/* 6b. Promote Chunk Modal (단어 하나) */}
      <PromoteChunkModal
        isOpen={isChunkModalOpen}
        onClose={() => setIsChunkModalOpen(false)}
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
