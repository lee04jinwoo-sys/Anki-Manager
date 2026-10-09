import React, { useEffect, useState } from 'react'
import { X, Check, SlidersHorizontal, Loader2 } from 'lucide-react'
import type { StepId, StepInfo } from '../../types/dashboard'
import { api } from '../../api/client'

interface MaintenanceModalProps {
  isOpen: boolean
  onClose: () => void
  onStarted: () => void
}

export const MaintenanceModal: React.FC<MaintenanceModalProps> = ({
  isOpen,
  onClose,
  onStarted,
}) => {
  const [steps, setSteps] = useState<StepInfo[]>([])
  const [selectedIds, setSelectedIds] = useState<Set<StepId>>(new Set())
  const [isLoading, setIsLoading] = useState(false)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!isOpen) return
    setIsLoading(true)
    setError(null)
    api
      .getMaintenanceSteps()
      .then((data) => {
        setSteps(data)
        const defaults = new Set<StepId>(
          data.filter((s) => s.default).map((s) => s.id),
        )
        setSelectedIds(defaults)
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : '스텝 목록 로드 실패')
      })
      .finally(() => setIsLoading(false))
  }, [isOpen])

  if (!isOpen) return null

  const toggleStep = (id: StepId) => {
    const next = new Set(selectedIds)
    if (next.has(id)) {
      next.delete(id)
    } else {
      next.add(id)
    }
    setSelectedIds(next)
  }

  const handleRun = async () => {
    if (selectedIds.size === 0) return
    setIsSubmitting(true)
    setError(null)
    try {
      const selectedList = Array.from(selectedIds)
      const res = await api.runMaintenance(selectedList)
      if (res.status === 'success') {
        onStarted()
        onClose()
      } else {
        setError(res.message || '작업 시작 실패')
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '실행 중 오류 발생')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm animate-fade-in">
      <div className="bg-apple-card border border-apple-border rounded-apple-lg max-w-lg w-full shadow-apple-modal overflow-hidden animate-scale-in">
        {/* Modal Header */}
        <div className="px-6 py-4 border-b border-apple-border flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-apple-sm bg-apple-blue/10 text-apple-blue">
              <SlidersHorizontal className="w-4 h-4" />
            </div>
            <div>
              <h2 className="text-sm font-semibold text-apple-text tracking-tight">
                통합 노트 정리 (Maintenance)
              </h2>
              <p className="text-xs text-apple-secondary">
                누락된 오디오, 빈 필드, 규칙별 덱 이동을 순차적으로 수행합니다.
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
        <div className="p-6">
          {error && (
            <div className="mb-4 p-3 rounded-apple-sm bg-apple-red/10 border border-apple-red/20 text-xs text-apple-red">
              {error}
            </div>
          )}

          {isLoading ? (
            <div className="py-12 flex flex-col items-center justify-center text-apple-secondary text-xs">
              <Loader2 className="w-5 h-5 animate-spin mb-2 text-apple-blue" />
              <span>정리 규칙 및 스텝 목록 로드 중...</span>
            </div>
          ) : (
            <div className="space-y-2.5">
              {steps.map((step) => {
                const isChecked = selectedIds.has(step.id)
                return (
                  <label
                    key={step.id}
                    onClick={() => toggleStep(step.id)}
                    className={`flex items-start gap-3 p-3 rounded-apple-sm border cursor-pointer select-none transition-all ${
                      isChecked
                        ? 'bg-apple-subtle border-apple-blue/40 shadow-apple-subtle'
                        : 'bg-apple-card border-apple-border hover:border-apple-borderStrong opacity-70'
                    }`}
                  >
                    <div
                      className={`w-4 h-4 mt-0.5 rounded flex items-center justify-center border transition-all ${
                        isChecked
                          ? 'bg-apple-blue border-apple-blue text-white'
                          : 'border-apple-borderStrong bg-apple-card'
                      }`}
                    >
                      {isChecked && <Check className="w-3 h-3 stroke-[3]" />}
                    </div>
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-semibold text-apple-text">
                          {step.label}
                        </span>
                        {step.default && (
                          <span className="text-[10px] px-1.5 py-0.2 rounded bg-apple-blue/10 text-apple-blue font-medium">
                            기본 권장
                          </span>
                        )}
                      </div>
                      <p className="text-[11px] text-apple-secondary mt-0.5">
                        {step.description}
                      </p>
                    </div>
                  </label>
                )
              })}
            </div>
          )}
        </div>

        {/* Modal Footer */}
        <div className="px-6 py-3.5 bg-apple-bg border-t border-apple-border flex items-center justify-between">
          <span className="text-xs text-apple-secondary">
            {selectedIds.size}개 단계 선택됨
          </span>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={onClose}
              disabled={isSubmitting}
              className="px-3.5 py-1.5 text-xs font-medium text-apple-text bg-apple-subtle border border-apple-border rounded-apple-sm hover:bg-apple-subtleHover transition-colors disabled:opacity-40"
            >
              취소
            </button>
            <button
              type="button"
              onClick={handleRun}
              disabled={selectedIds.size === 0 || isSubmitting}
              className="inline-flex items-center gap-1.5 px-4 py-1.5 text-xs font-medium text-white bg-apple-blue hover:bg-apple-blueHover rounded-apple-sm transition-all shadow-apple-subtle disabled:opacity-40"
            >
              {isSubmitting ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  <span>실행 중...</span>
                </>
              ) : (
                <span>정리 파이프라인 실행</span>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
