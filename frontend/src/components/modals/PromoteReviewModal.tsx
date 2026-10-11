import React, { useEffect, useRef, useState } from 'react'
import { ChevronDown, ChevronUp, Loader2, RotateCcw, X } from 'lucide-react'
import { api } from '../../api/client'
import type { LinkVocabItem } from '../../types/dashboard'
import { buildPromoteRequests, mapWithConcurrency, type EditableField, type ReviewRow } from '../../lib/promoteReview'

const CONCURRENCY = 4

const FIELDS: { key: EditableField; label: string; multiline?: boolean }[] = [
  { key: 'new_chunk', label: '청크' },
  { key: 'meaning', label: '뜻' },
  { key: 'example_1', label: '예문 1' },
  { key: 'trans_1', label: '번역 1' },
  { key: 'example_2', label: '예문 2' },
  { key: 'trans_2', label: '번역 2' },
  { key: 'explanation', label: '설명', multiline: true },
]

interface Props {
  isOpen: boolean
  items: LinkVocabItem[]
  onClose: () => void
  onStarted: () => void
}

/** 청크 승격 한 화면 검토: 단어마다 후보를 고르고 한 번에 승격한다. */
export const PromoteReviewModal: React.FC<Props> = ({ isOpen, items, onClose, onStarted }) => {
  const [rows, setRows] = useState<ReviewRow[]>([])
  const [expanded, setExpanded] = useState<number | null>(null)
  const [resetToNew, setResetToNew] = useState(true)
  const [addSentences, setAddSentences] = useState(true)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const loadId = useRef(0)

  const patch = (noteId: number, update: Partial<ReviewRow>) =>
    setRows((prev) => prev.map((r) => (r.noteId === noteId ? { ...r, ...update } : r)))

  const load = async (targets: LinkVocabItem[], refresh: boolean, myLoad: number) => {
    await mapWithConcurrency(
      targets,
      CONCURRENCY,
      (it) => api.getCollocations(it.word, refresh),
      (i, res) => {
        if (loadId.current !== myLoad) return // 창을 닫았거나 다시 열었다
        const it = targets[i]!
        if (res.ok) {
          const c = res.value.candidates
          patch(it.note_id, { status: 'ready', candidates: c, cached: res.value.cached, selected: c.length ? 0 : -1, edits: {} })
        } else {
          patch(it.note_id, { status: 'error', error: res.error instanceof Error ? res.error.message : '후보를 불러오지 못했습니다' })
        }
      },
    )
  }

  useEffect(() => {
    if (!isOpen) {
      loadId.current++
      return
    }
    const myLoad = ++loadId.current
    setError(null)
    setExpanded(null)
    setRows(
      items.map((it) => ({
        noteId: it.note_id,
        word: it.word,
        meaningBefore: it.meaning,
        lapses: it.lapses,
        status: 'loading',
        candidates: [],
        selected: 0,
        edits: {},
      })),
    )
    void load(items, false, myLoad)
  }, [isOpen, items])

  if (!isOpen) return null

  const retry = (row: ReviewRow, refresh: boolean) => {
    const it = items.find((x) => x.note_id === row.noteId)
    if (!it) return
    patch(row.noteId, { status: 'loading', error: undefined })
    void load([it], refresh, loadId.current)
  }

  const loaded = rows.filter((r) => r.status !== 'loading').length
  const requests = buildPromoteRequests(rows, { resetToNew, addSentences })
  const skipped = rows.filter((r) => r.status === 'ready' && r.selected < 0).length

  const submit = async () => {
    const lines = [
      `${requests.length}개 단어를 청크로 승격합니다${skipped ? ` (승격 안 함 ${skipped}개)` : ''}.`,
      resetToNew ? '⚠ 승격한 카드는 새 카드로 초기화됩니다 (승격 전 상태는 data/backups/promote/ 에 저장).' : '',
      loaded < rows.length ? `아직 후보를 불러오는 ${rows.length - loaded}개는 빠집니다.` : '',
      '진행할까요?',
    ].filter(Boolean)
    if (!window.confirm(lines.join('\n'))) return
    setIsSubmitting(true)
    setError(null)
    try {
      const res = await api.promoteBatch(requests)
      if (res.status !== 'success') {
        setError(res.message || '승격 작업을 시작하지 못했습니다.')
        return
      }
      onStarted()
      onClose()
    } catch (e) {
      setError(e instanceof Error ? e.message : '승격 요청 실패')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm">
      <div className="flex max-h-[90vh] w-full max-w-4xl flex-col rounded-apple-lg border border-apple-borderStrong bg-apple-card shadow-apple-modal">
        {/* header */}
        <div className="flex items-start justify-between gap-3 border-b border-apple-border p-5">
          <div>
            <h3 className="text-base font-semibold text-apple-text">청크 승격 검토 · {rows.length}개</h3>
            <p className="mt-0.5 text-xs text-apple-secondary">
              단어마다 후보를 고르세요. 1순위가 미리 선택돼 있습니다 · 후보 불러옴 {loaded}/{rows.length}
              {loaded < rows.length && <Loader2 className="ml-1 inline h-3 w-3 animate-spin" />}
            </p>
          </div>
          <button type="button" onClick={onClose} className="rounded p-1 text-apple-secondary hover:bg-apple-subtle" title="닫기">
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* options */}
        <div className="flex flex-wrap gap-4 border-b border-apple-border px-5 py-3 text-xs text-apple-secondary">
          <label className="inline-flex cursor-pointer items-center gap-1.5">
            <input type="checkbox" checked={resetToNew} onChange={(e) => setResetToNew(e.target.checked)} />
            새 카드로 초기화 (오답 기록을 끊고 새로 학습)
          </label>
          <label className="inline-flex cursor-pointer items-center gap-1.5">
            <input type="checkbox" checked={addSentences} onChange={(e) => setAddSentences(e.target.checked)} />
            예문 2개를 문장 덱에도 추가
          </label>
        </div>

        {/* rows */}
        <div className="flex-1 divide-y divide-apple-border overflow-y-auto">
          {rows.map((row) => {
            const cand = row.selected >= 0 ? row.candidates[row.selected] : undefined
            const isOpenRow = expanded === row.noteId
            return (
              <div key={row.noteId} className="px-5 py-3">
                <div className="flex flex-wrap items-baseline justify-between gap-2">
                  <div>
                    <span className="font-mono text-sm font-semibold text-apple-text">{row.word}</span>
                    <span className="ml-2 text-xs text-apple-secondary">
                      {row.meaningBefore}
                      {row.lapses !== undefined && ` · 오답 ${row.lapses}회`}
                    </span>
                  </div>
                  {row.status === 'ready' && (
                    <div className="flex items-center gap-2 text-[11px] text-apple-secondary">
                      {row.cached && <span>저장된 후보</span>}
                      <button type="button" onClick={() => retry(row, true)} className="inline-flex items-center gap-1 hover:text-apple-text" title="후보 새로 생성 (Gemini 호출)">
                        <RotateCcw className="h-3 w-3" /> 다시 생성
                      </button>
                    </div>
                  )}
                </div>

                {row.status === 'loading' && (
                  <div className="mt-2 flex items-center gap-2 text-xs text-apple-secondary">
                    <Loader2 className="h-3.5 w-3.5 animate-spin" /> 후보 찾는 중...
                  </div>
                )}
                {row.status === 'error' && (
                  <div className="mt-2 flex items-center gap-2 text-xs text-apple-orange">
                    {row.error}
                    <button type="button" onClick={() => retry(row, false)} className="rounded border border-apple-border px-2 py-0.5 text-apple-text hover:bg-apple-subtle">
                      다시 시도
                    </button>
                  </div>
                )}
                {row.status === 'ready' && (
                  <>
                    <div className="mt-2 flex flex-wrap gap-2">
                      {row.candidates.map((c, i) => (
                        <button
                          key={c.chunk + i}
                          type="button"
                          onClick={() => patch(row.noteId, { selected: i, edits: {} })}
                          className={`rounded-apple-sm border px-2.5 py-1.5 text-left text-xs transition-colors ${
                            row.selected === i
                              ? 'border-apple-blue bg-apple-blue/15 text-apple-text'
                              : 'border-apple-border text-apple-secondary hover:border-apple-borderStrong hover:text-apple-text'
                          }`}
                        >
                          <div className="font-mono font-semibold">{c.chunk}</div>
                          <div className="text-[11px] opacity-80">{c.meaning}</div>
                        </button>
                      ))}
                      <button
                        type="button"
                        onClick={() => patch(row.noteId, { selected: -1 })}
                        className={`rounded-apple-sm border px-2.5 py-1.5 text-xs ${
                          row.selected < 0 ? 'border-apple-borderStrong bg-apple-subtle text-apple-text' : 'border-apple-border text-apple-secondary hover:text-apple-text'
                        }`}
                      >
                        승격 안 함
                      </button>
                    </div>
                    {cand && (
                      <button
                        type="button"
                        onClick={() => setExpanded(isOpenRow ? null : row.noteId)}
                        className="mt-2 inline-flex items-center gap-1 text-[11px] text-apple-secondary hover:text-apple-text"
                      >
                        {isOpenRow ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
                        예문·설명 {isOpenRow ? '접기' : '보기/수정'}
                      </button>
                    )}
                    {cand && isOpenRow && (
                      <div className="mt-2 grid gap-2 sm:grid-cols-2">
                        {FIELDS.map((f) => {
                          const value = row.edits[f.key] ?? (f.key === 'new_chunk' ? cand.chunk : cand[f.key])
                          const onChange = (v: string) => patch(row.noteId, { edits: { ...row.edits, [f.key]: v } })
                          return (
                            <label key={f.key} className={`text-[11px] text-apple-secondary ${f.multiline ? 'sm:col-span-2' : ''}`}>
                              {f.label}
                              {f.multiline ? (
                                <textarea value={value} onChange={(e) => onChange(e.target.value)} rows={3}
                                  className="mt-0.5 w-full rounded-apple-sm border border-apple-border bg-apple-bg px-2 py-1 text-xs text-apple-text outline-none focus:border-apple-blue" />
                              ) : (
                                <input value={value} onChange={(e) => onChange(e.target.value)}
                                  className="mt-0.5 w-full rounded-apple-sm border border-apple-border bg-apple-bg px-2 py-1 text-xs text-apple-text outline-none focus:border-apple-blue" />
                              )}
                            </label>
                          )
                        })}
                      </div>
                    )}
                  </>
                )}
              </div>
            )
          })}
        </div>

        {/* footer */}
        <div className="flex flex-col gap-2 border-t border-apple-border p-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="text-xs text-apple-secondary">
            승격 {requests.length}개{skipped > 0 && ` · 승격 안 함 ${skipped}개`}
            {error && <span className="ml-2 text-apple-orange">{error}</span>}
          </div>
          <div className="flex gap-2">
            <button type="button" onClick={onClose} className="rounded-apple-sm border border-apple-border px-3 py-2 text-xs text-apple-text hover:bg-apple-subtle">
              취소
            </button>
            <button
              type="button"
              onClick={submit}
              disabled={isSubmitting || requests.length === 0}
              className="inline-flex items-center gap-1.5 rounded-apple-sm bg-apple-blue px-4 py-2 text-xs font-semibold text-white hover:bg-apple-blueHover disabled:opacity-50"
            >
              {isSubmitting && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
              {requests.length}개 한꺼번에 승격
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
