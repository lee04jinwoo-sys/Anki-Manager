export type StepId = 'fields' | 'audio' | 'deck_move' | 'pos' | 'duplicates'

export interface StepInfo {
  id: StepId
  label: string
  description: string
  default: boolean
}

export interface DeckCardCount {
  name: string
  display_name: string
  total: number
  new_remaining: number // 미학습 남은 새 카드 수 (is:new)
  due_today: number     // 오늘 복습 대상 카드 수 (is:due)
  studied_today: number // 오늘 복습 완료된 카드 수 (rated:1)
  due_tomorrow: number  // 내일 만료 예정 카드 수 (prop:due=1)
  due_7days: number     // 7일 내 만료 예정 카드 수 (prop:due<=7 prop:due>0)
  learning: number      // 학습 진행 중 (is:learn)
  mature: number        // 21일 이상 성숙 카드
  young: number         // 1~20일 젊은 카드
  suspended: number     // 보류 카드
  deck_leech_count: number // 덱 내 만성 오답 카드 수
  avg_interval_days: number // 평균 복습 주기 (일)
  avg_interval_months: number // 평균 복습 주기 (개월)
  avg_ease: number      // 평균 Ease (%)
  total_reps_est: number // 총 누적 복습 횟수 추정치
  today_retention: number // 금일 복습 정답률 (%)
  retention_30d: number // 최근 30일 복습 정답률 (%)
  mature_retention_30d: number // 최근 30일 성숙 카드 유지율 (%)
  retention_rate: number // 성숙 카드 비율 (Mature Card Ratio, %)
}

export interface LeechSummaryItem {
  note_id: number
  card_id: number
  word: string
  meaning: string
  lapses: number
  ease: number
  reps: number
}

export interface MaintenanceOverview {
  missing_audio_count: number
  missing_fields_count: number
  total_needs_count: number
}

export interface ObsidianInboxSummary {
  vocab_count: number
  sentence_count: number
  total_count: number
  available: boolean
}

export interface LogEntry {
  time: string
  message: string
  level: 'info' | 'success' | 'warn' | 'error'
  progress: number | null
}

export interface CandidateVocab {
  단어: string
  뜻: string
}

export interface Candidates {
  sentences: string[]
  vocab: CandidateVocab[]
}

export type JobStatus = 'idle' | 'running' | 'waiting_selection' | 'success' | 'error'

export interface JobState {
  is_running: boolean
  source: string
  progress: number
  current_step: string
  status: JobStatus
  logs: LogEntry[]
  meta: Record<string, unknown>
  candidates: Candidates
}

export interface DashboardResponse {
  connected: boolean
  anki_version: string | null
  decks: DeckCardCount[]
  maintenance: MaintenanceOverview
  leeches: LeechSummaryItem[]
  leech_total_count: number
  obsidian_inbox: ObsidianInboxSummary
  active_job: JobState
}

export interface ActionResult {
  status: 'success' | 'error'
  message: string
}

export interface LinkStats {
  total_vocab: number
  total_links: number
  linked_sentences: number
  unlinked_vocab: number
  leech_count?: number
}

export interface LinkVocabItem {
  note_id: number
  card_id?: number
  word: string
  meaning: string
  pos: string
  link_count: number
  lapses?: number
  ease?: number
  reps?: number
}

export interface LinkVocabResponse {
  total: number
  limit: number
  offset: number
  items: LinkVocabItem[]
}

export interface BatchGenerateResult {
  success: boolean
  created_count?: number
  results?: Array<{
    word: string
    sentence: string
    translation: string
    audio?: string
  }>
  message?: string
}
