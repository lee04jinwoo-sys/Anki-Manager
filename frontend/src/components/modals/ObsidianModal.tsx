import React, { useEffect, useState } from 'react'
import {
  X,
  Check,
  Inbox,
  Loader2,
  AlertCircle,
} from 'lucide-react'
import type { Candidates } from '../../types/dashboard'
import { api } from '../../api/client'
import { interpretExtractState } from '../../lib/jobPolling'

interface ObsidianModalProps {
  isOpen: boolean
  onClose: () => void
  onStarted: () => void
}

export const ObsidianModal: React.FC<ObsidianModalProps> = ({
  isOpen,
  onClose,
  onStarted,
}) => {
  const [isExtracting, setIsExtracting] = useState(false)
  const [candidates, setCandidates] = useState<Candidates>({ sentences: [], vocab: [] })
  const [selectedVocabIndices, setSelectedVocabIndices] = useState<Set<number>>(new Set())
  const [selectedSentenceIndices, setSelectedSentenceIndices] = useState<Set<number>>(new Set())
  const [isCommitting, setIsCommitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!isOpen) return

    let isMounted = true
    let pollInterval: ReturnType<typeof setInterval> | undefined
    setIsExtracting(true)
    setError(null)

    const fail = (message: string) => {
      if (pollInterval) clearInterval(pollInterval)
      if (isMounted) {
        setError(message)
        setIsExtracting(false)
      }
    }

    api
      .extractObsidian()
      .then((res) => {
        if (res.status !== 'success') {
          fail(res.message || 'Obsidian Inbox 추출을 시작하지 못했습니다.')
          return
        }
        // Poll for candidate data until the extract job settles
        pollInterval = setInterval(async () => {
          if (!isMounted) return
          try {
            const outcome = interpretExtractState(await api.getJobState())
            if (outcome.kind === 'wait') return
            if (outcome.kind === 'error') {
              fail(outcome.message)
              return
            }
            clearInterval(pollInterval)
            if (isMounted) {
              setCandidates(outcome.candidates)
              // Select all by default
              setSelectedVocabIndices(new Set(outcome.candidates.vocab.map((_, i) => i)))
              setSelectedSentenceIndices(new Set(outcome.candidates.sentences.map((_, i) => i)))
              setIsExtracting(false)
            }
          } catch (e) {
            console.error('Polling error:', e)
          }
        }, 1000)
      })
      .catch((err) => fail(err instanceof Error ? err.message : 'Obsidian Inbox 읽기 실패'))

    return () => {
      isMounted = false
      if (pollInterval) clearInterval(pollInterval)
    }
  }, [isOpen])

  if (!isOpen) return null

  const toggleVocab = (idx: number) => {
    const next = new Set(selectedVocabIndices)
    if (next.has(idx)) next.delete(idx)
    else next.add(idx)
    setSelectedVocabIndices(next)
  }

  const toggleSentence = (idx: number) => {
    const next = new Set(selectedSentenceIndices)
    if (next.has(idx)) next.delete(idx)
    else next.add(idx)
    setSelectedSentenceIndices(next)
  }

  const handleCommit = async () => {
    const chosenVocab = Array.from(selectedVocabIndices).map((i) => candidates.vocab[i]!)
    const chosenSentences = Array.from(selectedSentenceIndices).map(
      (i) => candidates.sentences[i]!,
    )

    if (chosenVocab.length === 0 && chosenSentences.length === 0) return

    setIsCommitting(true)
    setError(null)
    try {
      const res = await api.commitObsidian(chosenSentences, chosenVocab)
      if (res.status === 'success') {
        onStarted()
        onClose()
      } else {
        setError(res.message || '등록 요청 실패')
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '등록 중 오류 발생')
    } finally {
      setIsCommitting(false)
    }
  }

  const totalCandidates = candidates.vocab.length + candidates.sentences.length
  const totalSelected = selectedVocabIndices.size + selectedSentenceIndices.size

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm animate-fade-in">
      <div className="bg-apple-card border border-apple-border rounded-apple-lg max-w-2xl w-full shadow-apple-modal overflow-hidden animate-scale-in max-h-[85vh] flex flex-col">
        {/* Modal Header */}
        <div className="px-6 py-4 border-b border-apple-border flex items-center justify-between shrink-0">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-apple-sm bg-apple-blue/10 text-apple-blue">
              <Inbox className="w-4 h-4" />
            </div>
            <div>
              <h2 className="text-sm font-semibold text-apple-text tracking-tight">
                Obsidian Inbox 가져오기
              </h2>
              <p className="text-xs text-apple-secondary">
                Inbox 마크다운에서 추출된 후보를 선택하고 Gemini AI로 뜻/예문/오디오를 자동 생성합니다.
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 text-apple-secondary hover:text-apple-text rounded hover:bg-apple-bg transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Modal Body */}
        <div className="p-6 overflow-y-auto flex-1">
          {error && (
            <div className="mb-4 p-3 rounded-apple-sm bg-apple-red/10 border border-apple-red/20 text-xs text-apple-red flex items-start gap-2">
              <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
              <span>{error}</span>
            </div>
          )}

          {isExtracting ? (
            <div className="py-16 flex flex-col items-center justify-center text-apple-secondary text-xs">
              <Loader2 className="w-6 h-6 animate-spin mb-3 text-apple-blue" />
              <span>Obsidian Inbox 노트 파싱 중...</span>
            </div>
          ) : totalCandidates === 0 ? (
            <div className="py-16 text-center text-xs text-apple-secondary">
              Obsidian Inbox에 등록할 새로운 단어나 문장이 없습니다.
            </div>
          ) : (
            <div className="space-y-5">
              {/* Vocab Section */}
              {candidates.vocab.length > 0 && (
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs font-semibold text-apple-text">
                      단어 후보 ({candidates.vocab.length}개)
                    </span>
                    <button
                      type="button"
                      onClick={() => {
                        if (selectedVocabIndices.size === candidates.vocab.length) {
                          setSelectedVocabIndices(new Set())
                        } else {
                          setSelectedVocabIndices(
                            new Set(candidates.vocab.map((_, i) => i)),
                          )
                        }
                      }}
                      className="text-[11px] text-apple-blue hover:underline"
                    >
                      {selectedVocabIndices.size === candidates.vocab.length
                        ? '전체 해제'
                        : '전체 선택'}
                    </button>
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                    {candidates.vocab.map((v, idx) => {
                      const isChecked = selectedVocabIndices.has(idx)
                      return (
                        <div
                          key={idx}
                          onClick={() => toggleVocab(idx)}
                          className={`p-2.5 rounded-apple-sm border cursor-pointer select-none flex items-center gap-2.5 transition-all ${
                            isChecked
                              ? 'bg-apple-subtle border-apple-blue/40 shadow-apple-subtle'
                              : 'bg-apple-card border-apple-border opacity-70'
                          }`}
                        >
                          <div
                            className={`w-3.5 h-3.5 rounded flex items-center justify-center border transition-all ${
                              isChecked
                                ? 'bg-apple-blue border-apple-blue text-white'
                                : 'border-apple-borderStrong bg-apple-card'
                            }`}
                          >
                            {isChecked && <Check className="w-2.5 h-2.5 stroke-[3]" />}
                          </div>
                          <span className="text-xs font-semibold text-apple-text">
                            {v.단어}
                          </span>
                        </div>
                      )
                    })}
                  </div>
                </div>
              )}

              {/* Sentences Section */}
              {candidates.sentences.length > 0 && (
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs font-semibold text-apple-text">
                      문장 후보 ({candidates.sentences.length}개)
                    </span>
                    <button
                      type="button"
                      onClick={() => {
                        if (
                          selectedSentenceIndices.size ===
                          candidates.sentences.length
                        ) {
                          setSelectedSentenceIndices(new Set())
                        } else {
                          setSelectedSentenceIndices(
                            new Set(candidates.sentences.map((_, i) => i)),
                          )
                        }
                      }}
                      className="text-[11px] text-apple-blue hover:underline"
                    >
                      {selectedSentenceIndices.size === candidates.sentences.length
                        ? '전체 해제'
                        : '전체 선택'}
                    </button>
                  </div>
                  <div className="space-y-1.5">
                    {candidates.sentences.map((s, idx) => {
                      const isChecked = selectedSentenceIndices.has(idx)
                      return (
                        <div
                          key={idx}
                          onClick={() => toggleSentence(idx)}
                          className={`p-2.5 rounded-apple-sm border cursor-pointer select-none flex items-start gap-2.5 transition-all ${
                            isChecked
                              ? 'bg-apple-subtle border-apple-blue/40 shadow-apple-subtle'
                              : 'bg-apple-card border-apple-border opacity-70'
                          }`}
                        >
                          <div
                            className={`w-3.5 h-3.5 mt-0.5 rounded flex items-center justify-center border transition-all ${
                              isChecked
                                ? 'bg-apple-blue border-apple-blue text-white'
                                : 'border-apple-borderStrong bg-apple-card'
                            }`}
                          >
                            {isChecked && <Check className="w-2.5 h-2.5 stroke-[3]" />}
                          </div>
                          <span className="text-xs text-apple-text leading-relaxed">
                            {s}
                          </span>
                        </div>
                      )
                    })}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Modal Footer */}
        <div className="px-6 py-3.5 bg-apple-bg border-t border-apple-border flex items-center justify-between shrink-0">
          <span className="text-xs text-apple-secondary">
            총 {totalSelected}개 항목 선택됨
          </span>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={onClose}
              disabled={isCommitting}
              className="px-3.5 py-1.5 text-xs font-medium text-apple-text bg-apple-subtle border border-apple-border rounded-apple-sm hover:bg-apple-subtleHover transition-colors disabled:opacity-40"
            >
              취소
            </button>
            <button
              type="button"
              onClick={handleCommit}
              disabled={totalSelected === 0 || isCommitting}
              className="inline-flex items-center gap-1.5 px-4 py-1.5 text-xs font-medium text-white bg-apple-blue hover:bg-apple-blueHover rounded-apple-sm transition-all shadow-apple-subtle disabled:opacity-40"
            >
              {isCommitting ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  <span>등록 중...</span>
                </>
              ) : (
                <span>Anki 등록 및 AI 보강</span>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
