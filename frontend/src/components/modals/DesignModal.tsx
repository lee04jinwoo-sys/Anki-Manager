import React, { useState } from 'react'
import { X, Palette, Download, Upload, Loader2, CheckCircle2 } from 'lucide-react'
import { api } from '../../api/client'

interface DesignModalProps {
  isOpen: boolean
  onClose: () => void
  onStarted: () => void
}

export const DesignModal: React.FC<DesignModalProps> = ({
  isOpen,
  onClose,
  onStarted,
}) => {
  const [isExporting, setIsExporting] = useState(false)
  const [isImporting, setIsImporting] = useState(false)
  const [feedback, setFeedback] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  if (!isOpen) return null

  const handleExport = async () => {
    setIsExporting(true)
    setError(null)
    setFeedback(null)
    try {
      const res = await api.exportDesign()
      if (res.status === 'success') {
        onStarted()
        onClose()
      } else {
        setError(res.message || '백업 실패')
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '오류 발생')
    } finally {
      setIsExporting(false)
    }
  }

  const handleImport = async () => {
    setIsImporting(true)
    setError(null)
    setFeedback(null)
    try {
      const res = await api.importDesign()
      if (res.status === 'success') {
        onStarted()
        onClose()
      } else {
        setError(res.message || '복원 실패')
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '오류 발생')
    } finally {
      setIsImporting(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm animate-fade-in">
      <div className="bg-apple-card border border-apple-border rounded-apple-lg max-w-md w-full shadow-apple-modal overflow-hidden animate-scale-in">
        {/* Modal Header */}
        <div className="px-6 py-4 border-b border-apple-border flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-apple-sm bg-apple-blue/10 text-apple-blue">
              <Palette className="w-4 h-4" />
            </div>
            <div>
              <h2 className="text-sm font-semibold text-apple-text tracking-tight">
                카드 디자인 관리
              </h2>
              <p className="text-xs text-apple-secondary">
                JSON 설정 파일 기반으로 템플릿과 스타일을 백업하거나 복원합니다.
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
        <div className="p-6 space-y-4">
          {error && (
            <div className="p-3 rounded-apple-sm bg-apple-red/10 border border-apple-red/20 text-xs text-apple-red">
              {error}
            </div>
          )}

          {feedback && (
            <div className="p-3 rounded-apple-sm bg-apple-green/10 border border-apple-green/20 text-xs text-apple-green flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 shrink-0" />
              <span>{feedback}</span>
            </div>
          )}

          {/* Export Action Card */}
          <div className="p-4 rounded-apple-sm border border-apple-border bg-apple-subtle/50 flex items-center justify-between gap-4">
            <div>
              <div className="text-xs font-semibold text-apple-text">
                디자인 JSON 내보내기
              </div>
              <p className="text-[11px] text-apple-secondary mt-0.5">
                현재 Anki의 프론트/백 템플릿과 CSS를 data/design_config.json에 저장합니다.
              </p>
            </div>
            <button
              type="button"
              onClick={handleExport}
              disabled={isExporting || isImporting}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-apple-text bg-apple-card border border-apple-border hover:border-apple-borderStrong rounded-apple-sm transition-all shadow-apple-subtle disabled:opacity-40 shrink-0"
            >
              {isExporting ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
              ) : (
                <Download className="w-3.5 h-3.5 text-apple-secondary" />
              )}
              <span>내보내기</span>
            </button>
          </div>

          {/* Import Action Card */}
          <div className="p-4 rounded-apple-sm border border-apple-border bg-apple-subtle/50 flex items-center justify-between gap-4">
            <div>
              <div className="text-xs font-semibold text-apple-text">
                디자인 JSON 복원
              </div>
              <p className="text-[11px] text-apple-secondary mt-0.5">
                data/design_config.json 파일의 내용을 Anki 모델에 반영합니다.
              </p>
            </div>
            <button
              type="button"
              onClick={handleImport}
              disabled={isExporting || isImporting}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-apple-text bg-apple-card border border-apple-border hover:border-apple-borderStrong rounded-apple-sm transition-all shadow-apple-subtle disabled:opacity-40 shrink-0"
            >
              {isImporting ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
              ) : (
                <Upload className="w-3.5 h-3.5 text-apple-secondary" />
              )}
              <span>가져오기</span>
            </button>
          </div>
        </div>

        {/* Modal Footer */}
        <div className="px-6 py-3.5 bg-apple-bg border-t border-apple-border flex justify-end">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-1.5 text-xs font-medium text-apple-text bg-apple-subtle border border-apple-border rounded-apple-sm hover:bg-apple-subtleHover transition-colors"
          >
            닫기
          </button>
        </div>
      </div>
    </div>
  )
}
