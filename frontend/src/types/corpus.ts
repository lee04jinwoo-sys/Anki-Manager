export interface CollocationCandidate {
  chunk: string
  meaning: string
  pos: string
  tier: string
  rank: number
  example_1: string
  trans_1: string
  example_2: string
  trans_2: string
  explanation: string
  frequency_score?: number
}

export interface CollocationResponse {
  original_word: string
  original_rank: number
  original_tier: string
  candidates: CollocationCandidate[]
  cached?: boolean
}

export interface PromoteChunkRequest {
  note_id: number
  new_chunk: string
  meaning: string
  pos?: string
  example_1: string
  trans_1: string
  example_2: string
  trans_2: string
  explanation?: string
  add_sentences_to_deck?: boolean
  reset_to_new?: boolean
}

export interface PromoteChunkResponse {
  success: boolean
  note_id: number
  new_chunk: string
  cards_reset_count: number
  sentences_added_count: number
  error?: string
}

export interface CorpusAuditStats {
  total_notes: number
  total_cards: number
  tier_distribution: Record<string, number>
  waste_leech_count: number
  top_waste_leeches: Array<{
    note_id: number
    word: string
    meaning: string
    rank: number
    tier: string
    lapses: number
    is_waste_leech: boolean
  }>
  generated_at?: string | null
}
