import type {
  ActionResult,
  CandidateVocab,
  DashboardResponse,
  JobState,
  StepId,
  StepInfo,
  LinkStats,
  LinkVocabResponse,
  LinkVocabItem,
  BatchGenerateResult,
  LeechAction,
} from '../types/dashboard'
import type { StatsOverview } from '../types/stats'

const API_BASE = '/api'

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
    ...options,
  })

  if (!res.ok) {
    const errorText = await res.text()
    throw new Error(`API Error (${res.status}): ${errorText}`)
  }

  return res.json() as Promise<T>
}

export const api = {
  // Dashboard
  getDashboard: (): Promise<DashboardResponse> => request<DashboardResponse>('/dashboard'),
  getStatsOverview: (lang = 'en'): Promise<StatsOverview> =>
    request<StatsOverview>(`/stats/overview?lang=${lang}`),

  // Maintenance
  getMaintenanceSteps: (): Promise<StepInfo[]> => request<StepInfo[]>('/organize/steps'),
  runMaintenance: (steps?: StepId[]): Promise<ActionResult> =>
    request<ActionResult>('/organize/run', {
      method: 'POST',
      body: JSON.stringify(steps ? { steps } : {}),
    }),
  syncAnkiWeb: (): Promise<ActionResult> =>
    request<ActionResult>('/organize/sync', { method: 'POST' }),

  // Background Jobs
  getJobState: (): Promise<JobState> => request<JobState>('/workflow/state'),
  cancelJob: (): Promise<ActionResult> =>
    request<ActionResult>('/workflow/cancel', { method: 'POST' }),

  // Obsidian Import
  extractObsidian: (): Promise<ActionResult> =>
    request<ActionResult>('/workflow/extract', {
      method: 'POST',
      body: JSON.stringify({ source: 'obsidian' }),
    }),
  commitObsidian: (
    selectedSentences: string[],
    selectedVocab: CandidateVocab[],
  ): Promise<ActionResult> =>
    request<ActionResult>('/workflow/commit', {
      method: 'POST',
      body: JSON.stringify({
        source: 'obsidian',
        selected_sentences: selectedSentences,
        selected_vocab: selectedVocab,
      }),
    }),

  // Design
  exportDesign: (): Promise<ActionResult> =>
    request<ActionResult>('/design/export', { method: 'POST' }),
  importDesign: (): Promise<ActionResult> =>
    request<ActionResult>('/design/import', { method: 'POST' }),

  // Link Management
  getLinkStats: (lang = 'en'): Promise<LinkStats> =>
    request<LinkStats>(`/links/stats?lang=${lang}`),
  getLinkVocab: (params: {
    limit?: number
    offset?: number
    filter_mode?: string | null
    max_links?: number | null
    search?: string
    lang?: string
  }): Promise<LinkVocabResponse> => {
    const searchParams = new URLSearchParams()
    if (params.limit !== undefined) searchParams.set('limit', String(params.limit))
    if (params.offset !== undefined) searchParams.set('offset', String(params.offset))
    if (params.filter_mode) searchParams.set('filter_mode', params.filter_mode)
    if (params.max_links !== undefined && params.max_links !== null) {
      searchParams.set('max_links', String(params.max_links))
    }
    if (params.search) searchParams.set('search', params.search)
    searchParams.set('lang', params.lang || 'en')
    const qs = searchParams.toString()
    return request<LinkVocabResponse>(`/links/vocab${qs ? `?${qs}` : ''}`)
  },
  getLinkRandom: (count = 20, lang = 'en'): Promise<{ count: number; items: LinkVocabItem[] }> =>
    request<{ count: number; items: LinkVocabItem[] }>(`/links/random?count=${count}&lang=${lang}`),
  getLinkLeech: (count = 20, lang = 'en'): Promise<{ count: number; items: LinkVocabItem[] }> =>
    request<{ count: number; items: LinkVocabItem[] }>(`/links/leech?count=${count}&lang=${lang}`),
  scanLinks: (lang = 'en'): Promise<{ success: boolean; message: string; data: Record<string, unknown> }> =>
    request<{ success: boolean; message: string; data: Record<string, unknown> }>(`/links/scan?lang=${lang}`, {
      method: 'POST',
    }),
  batchGenerateSentences: (
    words: { note_id: number; word: string; meaning: string }[],
    generateAudio = true,
    lang = 'en',
  ): Promise<BatchGenerateResult> =>
    request<BatchGenerateResult>('/links/batch-generate', {
      method: 'POST',
      body: JSON.stringify({ words, generate_audio: generateAudio, lang }),
    }),

  // Leech batch actions (review_today / reset / examples) — runs as a background job
  applyLeechActions: (
    items: { note_id: number; word: string; meaning: string; action: LeechAction }[],
  ): Promise<ActionResult> =>
    request<ActionResult>('/leech/apply', { method: 'POST', body: JSON.stringify({ items }) }),

  // Corpus & Chunk Promotion
  getCorpusAuditStats: (): Promise<import('../types/corpus').CorpusAuditStats> =>
    request<import('../types/corpus').CorpusAuditStats>('/corpus/audit-stats'),
  getCollocations: (word: string, refresh = false): Promise<import('../types/corpus').CollocationResponse> =>
    request<import('../types/corpus').CollocationResponse>(
      `/corpus/collocations?word=${encodeURIComponent(word)}${refresh ? '&refresh=true' : ''}`,
    ),
  promoteBatch: (items: import('../types/corpus').PromoteChunkRequest[]): Promise<ActionResult> =>
    request<ActionResult>('/corpus/promote-batch', { method: 'POST', body: JSON.stringify({ items }) }),
  promoteChunk: (
    req: import('../types/corpus').PromoteChunkRequest,
  ): Promise<import('../types/corpus').PromoteChunkResponse> =>
    request<import('../types/corpus').PromoteChunkResponse>('/corpus/promote-chunk', {
      method: 'POST',
      body: JSON.stringify(req),
    }),
}

