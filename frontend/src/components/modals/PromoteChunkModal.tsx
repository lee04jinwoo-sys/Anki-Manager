import React, { useState, useEffect } from 'react'
import {
  X,
  Sparkles,
  Loader2,
  CheckCircle2,
  AlertCircle,
  Flame,
} from 'lucide-react'
import { api } from '../../api/client'
import type { LinkVocabItem } from '../../types/dashboard'
import type {
  CollocationCandidate,
  CollocationResponse,
  PromoteChunkResponse,
} from '../../types/corpus'

interface PromoteChunkModalProps {
  isOpen: boolean
  onClose: () => void
  targetItem: LinkVocabItem | null
  onPromoted?: (result: PromoteChunkResponse) => void
}

export const PromoteChunkModal: React.FC<PromoteChunkModalProps> = ({
  isOpen,
  onClose,
  targetItem,
  onPromoted,
}) => {
  const [isLoading, setIsLoading] = useState(false)
  const [isPromoting, setIsPromoting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [successMsg, setSuccessMsg] = useState<string | null>(null)

  const [collocations, setCollocations] = useState<CollocationResponse | null>(null)
  const [selectedIndex, setSelectedIndex] = useState<number>(0)

  // Editable fields for the selected candidate
  const [selectedChunk, setSelectedChunk] = useState('')
  const [selectedMeaning, setSelectedMeaning] = useState('')
  const [selectedPos, setSelectedPos] = useState('v')
  const [example1, setExample1] = useState('')
  const [trans1, setTrans1] = useState('')
  const [example2, setExample2] = useState('')
  const [trans2, setTrans2] = useState('')
  const [explanation, setExplanation] = useState('')

  // Options
  const [addSentences, setAddSentences] = useState(true)
  const [resetToNew, setResetToNew] = useState(true)

  // Fetch collocations when targetItem changes
  useEffect(() => {
    if (!isOpen || !targetItem) {
      setCollocations(null)
      setError(null)
      setSuccessMsg(null)
      return
    }

    loadCollocations(false)
  }, [isOpen, targetItem])

  // refresh=true 면 저장된 후보를 무시하고 Gemini로 새로 만든다
  const loadCollocations = async (refresh: boolean) => {
    if (!targetItem) return
    setIsLoading(true)
    setError(null)
    try {
      const res = await api.getCollocations(targetItem.word, refresh)
      setCollocations(res)
      if (res.candidates && res.candidates.length > 0 && res.candidates[0]) {
        applyCandidate(res.candidates[0], 0)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '고빈도 청크 후보를 탐색하는 중 오류가 발생했습니다.')
    } finally {
      setIsLoading(false)
    }
  }

  const applyCandidate = (cand: CollocationCandidate, idx: number) => {
    setSelectedIndex(idx)
    setSelectedChunk(cand.chunk)
    setSelectedMeaning(cand.meaning)
    setSelectedPos(cand.pos || 'v')
    setExample1(cand.example_1)
    setTrans1(cand.trans_1)
    setExample2(cand.example_2)
    setTrans2(cand.trans_2)
    setExplanation(cand.explanation)
  }

  const handlePromote = async () => {
    if (!targetItem || !selectedChunk.trim()) return
    if (
      resetToNew &&
      !window.confirm(
        `'${targetItem.word}' 카드가 '${selectedChunk.trim()}'(으)로 바뀌고 학습 이력(간격·복습 횟수)이 초기화됩니다.\n` +
          '원본은 data/backups/promote/ 에 저장됩니다. 진행할까요?',
      )
    )
      return

    setIsPromoting(true)
    setError(null)
    setSuccessMsg(null)

    try {
      const res = await api.promoteChunk({
        note_id: targetItem.note_id,
        new_chunk: selectedChunk.trim(),
        meaning: selectedMeaning.trim(),
        pos: selectedPos,
        example_1: example1.trim(),
        trans_1: trans1.trim(),
        example_2: example2.trim(),
        trans_2: trans2.trim(),
        explanation: explanation.trim(),
        add_sentences_to_deck: addSentences,
        reset_to_new: resetToNew,
      })

      setSuccessMsg(
        `'${targetItem.word}' 단어가 '${res.new_chunk}' 청크로 성공적으로 승격되었습니다!`,
      )
      if (onPromoted) {
        onPromoted(res)
      }
      setTimeout(() => {
        onClose()
      }, 1500)
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : '청크 승격 실행 중 오류가 발생했습니다.',
      )
    } finally {
      setIsPromoting(false)
    }
  }

  if (!isOpen || !targetItem) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-fade-in">
      <div className="relative w-full max-w-2xl bg-neutral-900 border border-neutral-700/80 rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-neutral-800 bg-neutral-950/40">
          <div className="flex items-center gap-2.5">
            <div className="p-2 bg-amber-500/10 text-amber-400 rounded-xl border border-amber-500/20">
              <Sparkles className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-base font-semibold text-white">
                고빈도 청크 승격 (Upgrade to Chunk)
              </h3>
              <p className="text-xs text-neutral-400">
                고립된 단어를 전치사/목적어가 결합된 실전 관용 청크로 재정의하여 오답 간섭을 원천 차단합니다.
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 text-neutral-400 hover:text-white rounded-lg hover:bg-neutral-800 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content Body */}
        <div className="flex-1 overflow-y-auto p-6 space-y-5">
          {/* Target Word Info Banner */}
          <div className="flex items-center justify-between p-3.5 bg-neutral-800/60 border border-neutral-700/60 rounded-xl">
            <div className="flex items-center gap-3">
              <span className="text-lg font-bold text-white tracking-wide">
                {targetItem.word}
              </span>
              <span className="text-sm text-neutral-400">
                {targetItem.meaning}
              </span>
            </div>
            <div className="flex items-center gap-2">
              {targetItem.lapses !== undefined && targetItem.lapses > 0 && (
                <span className="flex items-center gap-1 px-2.5 py-1 text-xs font-medium text-rose-300 bg-rose-500/15 border border-rose-500/30 rounded-lg">
                  <Flame className="w-3.5 h-3.5" />
                  누적 오답 {targetItem.lapses}회
                </span>
              )}
              {collocations && (
                <span className="px-2 py-1 text-xs font-medium text-neutral-300 bg-neutral-700/50 rounded-lg">
                  Rank #{collocations.original_rank.toLocaleString()}
                </span>
              )}
            </div>
          </div>

          {/* Loader or Error */}
          {isLoading && (
            <div className="flex flex-col items-center justify-center py-10 space-y-3">
              <Loader2 className="w-8 h-8 text-amber-400 animate-spin" />
              <p className="text-sm text-neutral-400">
                구글 코퍼스 및 AI 기반 고빈도 연어 후보를 탐색하고 있습니다...
              </p>
            </div>
          )}

          {error && (
            <div className="flex items-center gap-2.5 p-3.5 bg-rose-500/10 border border-rose-500/20 rounded-xl text-rose-300 text-sm">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {successMsg && (
            <div className="flex items-center gap-2.5 p-3.5 bg-emerald-500/10 border border-emerald-500/20 rounded-xl text-emerald-300 text-sm">
              <CheckCircle2 className="w-4 h-4 shrink-0" />
              <span>{successMsg}</span>
            </div>
          )}

          {/* Candidate Selection Cards */}
          {!isLoading && collocations && collocations.candidates.length > 0 && (
            <div>
              <div className="mb-2 flex items-center justify-between gap-2">
                <label className="block text-xs font-medium text-neutral-400">
                  추천된 고빈도 연어 / 청크 후보 (클릭하여 선택)
                  {collocations.cached && <span className="ml-2 text-neutral-500">· 저장된 후보</span>}
                </label>
                <button
                  type="button"
                  onClick={() => loadCollocations(true)}
                  className="rounded-md border border-neutral-700 px-2 py-0.5 text-[11px] text-neutral-400 hover:bg-neutral-800"
                  title="저장된 후보를 무시하고 새로 생성 (Gemini 호출)"
                >
                  다시 생성
                </button>
              </div>
              <div className="grid grid-cols-1 gap-2.5">
                {collocations.candidates.map((cand, idx) => {
                  const isSelected = selectedIndex === idx
                  return (
                    <div
                      key={idx}
                      onClick={() => applyCandidate(cand, idx)}
                      className={`cursor-pointer p-3.5 rounded-xl border transition-all ${
                        isSelected
                          ? 'bg-amber-500/10 border-amber-500/50 ring-1 ring-amber-500/30'
                          : 'bg-neutral-800/40 border-neutral-700/50 hover:bg-neutral-800 hover:border-neutral-600'
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <span className="font-semibold text-sm text-amber-300">
                            {cand.chunk}
                          </span>
                          <span className="px-1.5 py-0.5 text-[11px] font-bold rounded bg-amber-500/20 text-amber-300 border border-amber-500/30">
                            [{cand.pos || 'v'}]
                          </span>
                          <span className="text-xs text-neutral-400">
                            • {cand.meaning}
                          </span>
                        </div>
                        <span className="text-xs px-2 py-0.5 rounded-md font-medium bg-neutral-700/60 text-neutral-300 border border-neutral-600/50">
                          {cand.tier.replace('freq::', '')}
                        </span>
                      </div>
                      <p className="mt-1.5 text-xs text-neutral-400 line-clamp-1">
                        예문: {cand.example_1}
                      </p>
                    </div>
                  )
                })}
              </div>
            </div>
          )}

          {/* Form Fields for Selected Chunk */}
          {!isLoading && collocations && collocations.candidates.length > 0 && (
            <div className="space-y-3.5 pt-2 border-t border-neutral-800">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-neutral-400 mb-1">
                    새 단어/청크 (표제어)
                  </label>
                  <input
                    type="text"
                    value={selectedChunk}
                    onChange={(e) => setSelectedChunk(e.target.value)}
                    className="w-full px-3 py-2 text-sm bg-neutral-950 border border-neutral-700 rounded-lg text-white focus:outline-none focus:border-amber-500"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-neutral-400 mb-1">
                    새 한국어 뜻
                  </label>
                  <input
                    type="text"
                    value={selectedMeaning}
                    onChange={(e) => setSelectedMeaning(e.target.value)}
                    className="w-full px-3 py-2 text-sm bg-neutral-950 border border-neutral-700 rounded-lg text-white focus:outline-none focus:border-amber-500"
                  />
                </div>
              </div>

              {/* Functional POS Selector */}
              <div>
                <label className="block text-xs font-medium text-neutral-400 mb-1.5">
                  기능 품사 (Functional POS)
                </label>
                <div className="flex flex-wrap items-center gap-1.5">
                  {[
                    { value: 'v', label: 'v (동사구)' },
                    { value: 'n', label: 'n (명사구)' },
                    { value: 'adj', label: 'adj (형용사구)' },
                    { value: 'adv', label: 'adv (부사구)' },
                    { value: 'prep', label: 'prep (전치사구)' },
                    { value: 'idiom', label: 'idiom (관용구)' },
                  ].map((p) => {
                    const isSelected = selectedPos === p.value
                    return (
                      <button
                        key={p.value}
                        type="button"
                        onClick={() => setSelectedPos(p.value)}
                        className={`px-2.5 py-1 text-xs font-medium rounded-lg border transition-all ${
                          isSelected
                            ? 'bg-amber-400 text-black border-amber-300 font-bold shadow-sm'
                            : 'bg-neutral-800/80 text-neutral-300 border-neutral-700 hover:bg-neutral-700'
                        }`}
                      >
                        {p.label}
                      </button>
                    )
                  })}
                </div>
              </div>

              {/* Examples */}
              <div className="p-3 bg-neutral-950/60 rounded-xl border border-neutral-800 space-y-2.5">
                <div>
                  <label className="block text-xs font-medium text-neutral-400 mb-1">
                    예문 1 (영문 & 해석)
                  </label>
                  <input
                    type="text"
                    value={example1}
                    onChange={(e) => setExample1(e.target.value)}
                    placeholder="Example sentence 1"
                    className="w-full px-2.5 py-1.5 text-xs bg-neutral-900 border border-neutral-700 rounded-md text-white mb-1 focus:outline-none focus:border-amber-500"
                  />
                  <input
                    type="text"
                    value={trans1}
                    onChange={(e) => setTrans1(e.target.value)}
                    placeholder="한국어 해석 1"
                    className="w-full px-2.5 py-1.5 text-xs bg-neutral-900 border border-neutral-750 rounded-md text-neutral-300 focus:outline-none focus:border-amber-500"
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-neutral-400 mb-1">
                    예문 2 (영문 & 해석)
                  </label>
                  <input
                    type="text"
                    value={example2}
                    onChange={(e) => setExample2(e.target.value)}
                    placeholder="Example sentence 2"
                    className="w-full px-2.5 py-1.5 text-xs bg-neutral-900 border border-neutral-700 rounded-md text-white mb-1 focus:outline-none focus:border-amber-500"
                  />
                  <input
                    type="text"
                    value={trans2}
                    onChange={(e) => setTrans2(e.target.value)}
                    placeholder="한국어 해석 2"
                    className="w-full px-2.5 py-1.5 text-xs bg-neutral-900 border border-neutral-750 rounded-md text-neutral-300 focus:outline-none focus:border-amber-500"
                  />
                </div>
              </div>

              {/* Checkboxes */}
              <div className="flex flex-col gap-2 pt-1 text-xs text-neutral-300">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={addSentences}
                    onChange={(e) => setAddSentences(e.target.checked)}
                    className="w-4 h-4 rounded border-neutral-700 text-amber-500 focus:ring-0 bg-neutral-900"
                  />
                  <span>
                    문장 덱(Sentence)에 위 예문 2개를 <strong>Google Chirp3-HD 최고음질 오디오</strong>와 함께 자동 적재
                  </span>
                </label>
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={resetToNew}
                    onChange={(e) => setResetToNew(e.target.checked)}
                    className="w-4 h-4 rounded border-neutral-700 text-amber-500 focus:ring-0 bg-neutral-900"
                  />
                  <span>
                    이 카드를 <strong>완전 새 카드(New Card)</strong>로 리셋하고 Ease Factor를 <strong>250%</strong>로 복원 (과거 오답 0회 리셋)
                  </span>
                </label>
              </div>
            </div>
          )}
        </div>

        {/* Footer Actions */}
        <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-neutral-800 bg-neutral-950/40">
          <button
            onClick={onClose}
            disabled={isPromoting}
            className="px-4 py-2 text-sm font-medium text-neutral-400 hover:text-white hover:bg-neutral-800 rounded-xl transition-colors"
          >
            취소
          </button>
          <button
            onClick={handlePromote}
            disabled={isPromoting || isLoading || !selectedChunk.trim()}
            className="flex items-center gap-2 px-5 py-2 text-sm font-medium text-black bg-amber-400 hover:bg-amber-300 rounded-xl transition-all shadow-lg shadow-amber-400/20 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isPromoting ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                <span>승격 실행 중...</span>
              </>
            ) : (
              <>
                <Sparkles className="w-4 h-4" />
                <span>1-클릭 청크 승격 실행</span>
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  )
}
