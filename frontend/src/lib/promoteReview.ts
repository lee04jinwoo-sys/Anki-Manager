import type { CollocationCandidate, PromoteChunkRequest } from '../types/corpus'

export type Settled<R> = { ok: true; value: R } | { ok: false; error: unknown }

/** 최대 limit개씩 동시에 실행. 결과 순서는 입력 순서. onSettled는 하나 끝날 때마다 불린다. */
export async function mapWithConcurrency<T, R>(
  items: T[],
  limit: number,
  fn: (item: T, index: number) => Promise<R>,
  onSettled?: (index: number, result: Settled<R>) => void,
): Promise<Settled<R>[]> {
  const out: Settled<R>[] = new Array(items.length)
  let next = 0
  const worker = async () => {
    while (next < items.length) {
      const i = next++
      try {
        out[i] = { ok: true, value: await fn(items[i]!, i) }
      } catch (error) {
        out[i] = { ok: false, error }
      }
      onSettled?.(i, out[i]!)
    }
  }
  await Promise.all(Array.from({ length: Math.min(limit, items.length) }, worker))
  return out
}

export type EditableField = 'new_chunk' | 'meaning' | 'example_1' | 'trans_1' | 'example_2' | 'trans_2' | 'explanation'

export interface ReviewRow {
  noteId: number
  word: string
  meaningBefore?: string
  lapses?: number
  status: 'loading' | 'ready' | 'error'
  error?: string
  candidates: CollocationCandidate[]
  cached?: boolean
  /** 선택한 후보 번호. -1 = 승격 안 함 */
  selected: number
  /** 사용자가 고친 값 (후보를 바꾸면 비운다) */
  edits: Partial<Record<EditableField, string>>
}

/** 선택된 후보(+수정 사항)로 승격 요청을 만든다. 승격 안 함·아직 못 불러온 단어는 뺀다. */
export function buildPromoteRequests(
  rows: ReviewRow[],
  opts: { resetToNew: boolean; addSentences: boolean },
): PromoteChunkRequest[] {
  const reqs: PromoteChunkRequest[] = []
  for (const r of rows) {
    if (r.status !== 'ready' || r.selected < 0) continue
    const c = r.candidates[r.selected]
    if (!c) continue
    const v = (k: EditableField, fallback: string) => (r.edits[k] ?? fallback).trim()
    reqs.push({
      note_id: r.noteId,
      new_chunk: v('new_chunk', c.chunk),
      meaning: v('meaning', c.meaning),
      pos: c.pos,
      example_1: v('example_1', c.example_1),
      trans_1: v('trans_1', c.trans_1),
      example_2: v('example_2', c.example_2),
      trans_2: v('trans_2', c.trans_2),
      explanation: v('explanation', c.explanation),
      add_sentences_to_deck: opts.addSentences,
      reset_to_new: opts.resetToNew,
    })
  }
  return reqs
}
