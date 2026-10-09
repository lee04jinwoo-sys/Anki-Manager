import React, { useState } from 'react'
import {
  ChevronUp,
  ChevronDown,
  Loader2,
  CheckCircle2,
  AlertCircle,
  Terminal,
} from 'lucide-react'
import type { JobState } from '../types/dashboard'
import { api } from '../api/client'

interface JobDrawerProps {
  job: JobState
  onCancelSuccess: () => void
}

export const JobDrawer: React.FC<JobDrawerProps> = ({ job, onCancelSuccess }) => {
  const [isExpanded, setIsExpanded] = useState(false)
  const [isCanceling, setIsCanceling] = useState(false)

  // Only render if running, or recent success/error with logs
  if (job.status === 'idle' && !job.is_running && job.logs.length === 0) {
    return null
  }

  const handleCancel = async () => {
    setIsCanceling(true)
    try {
      await api.cancelJob()
      onCancelSuccess()
    } catch (err) {
      console.error('Failed to cancel job:', err)
    } finally {
      setIsCanceling(false)
    }
  }

  const isRunning = job.is_running || job.status === 'running'

  return (
    <div className="fixed bottom-4 right-4 z-40 max-w-lg w-full px-2 sm:px-0 transition-all">
      <div className="bg-apple-card border border-apple-borderStrong rounded-apple shadow-apple-modal overflow-hidden">
        {/* Header Bar */}
        <div className="p-3.5 flex items-center justify-between gap-3 bg-apple-card border-b border-apple-border">
          <div className="flex items-center gap-2.5 min-w-0">
            {isRunning ? (
              <Loader2 className="w-4 h-4 text-apple-blue animate-spin shrink-0" />
            ) : job.status === 'success' ? (
              <CheckCircle2 className="w-4 h-4 text-apple-green shrink-0" />
            ) : job.status === 'error' ? (
              <AlertCircle className="w-4 h-4 text-apple-red shrink-0" />
            ) : (
              <Terminal className="w-4 h-4 text-apple-secondary shrink-0" />
            )}

            <div className="min-w-0">
              <div className="text-xs font-semibold text-apple-text truncate">
                {job.source || '작업 상태'}
              </div>
              <div className="text-[11px] text-apple-secondary truncate">
                {job.current_step}
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2 shrink-0">
            {/* Progress Percentage */}
            {isRunning && (
              <span className="text-xs font-mono font-semibold text-apple-blue">
                {job.progress}%
              </span>
            )}

            {/* Cancel Button */}
            {isRunning && (
              <button
                type="button"
                onClick={handleCancel}
                disabled={isCanceling}
                className="text-[11px] text-apple-red hover:bg-apple-red/10 px-2 py-0.5 rounded transition-colors disabled:opacity-40"
              >
                {isCanceling ? '취소 중...' : '중단'}
              </button>
            )}

            {/* Expand / Collapse Button */}
            <button
              type="button"
              onClick={() => setIsExpanded(!isExpanded)}
              className="p-1 text-apple-secondary hover:text-apple-text rounded hover:bg-apple-bg transition-colors"
              title={isExpanded ? '로그 접기' : '로그 펼치기'}
            >
              {isExpanded ? (
                <ChevronDown className="w-4 h-4" />
              ) : (
                <ChevronUp className="w-4 h-4" />
              )}
            </button>
          </div>
        </div>

        {/* Live Progress Bar */}
        {isRunning && (
          <div className="h-1 bg-apple-bg w-full overflow-hidden">
            <div
              className="h-full bg-apple-blue transition-all duration-300 ease-out"
              style={{ width: `${Math.max(5, Math.min(100, job.progress))}%` }}
            />
          </div>
        )}

        {/* Expanded Terminal Logs */}
        {isExpanded && (
          <div className="p-3 bg-neutral-900 text-neutral-200 font-mono text-[11px] max-h-56 overflow-y-auto space-y-1.5 selection:bg-neutral-700">
            {job.logs.length === 0 ? (
              <div className="text-neutral-500 italic">로그가 없습니다.</div>
            ) : (
              job.logs.map((log, idx) => (
                <div key={idx} className="flex items-start gap-2 leading-relaxed">
                  <span className="text-neutral-500 shrink-0">{log.time}</span>
                  <span
                    className={
                      log.level === 'error'
                        ? 'text-red-400 font-semibold'
                        : log.level === 'success'
                        ? 'text-emerald-400'
                        : log.level === 'warn'
                        ? 'text-amber-300'
                        : 'text-neutral-300'
                    }
                  >
                    {log.message}
                  </span>
                </div>
              ))
            )}
          </div>
        )}
      </div>
    </div>
  )
}
