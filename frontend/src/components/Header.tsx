import React from 'react'
import { RefreshCw } from 'lucide-react'
import type { DashboardResponse } from '../types/dashboard'

interface HeaderProps {
  data: DashboardResponse | null
  isLoading: boolean
  onRefresh: () => void
}

export const Header: React.FC<HeaderProps> = ({
  data,
  isLoading,
  onRefresh,
}) => {
  const isConnected = data?.connected ?? false

  return (
    <header className="sticky top-0 z-30 bg-apple-card/80 backdrop-blur-md border-b border-apple-border px-6 py-3.5 transition-all">
      <div className="max-w-7xl mx-auto flex items-center justify-between gap-4">
        {/* Left: Branding & Connection Status */}
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-apple-sm bg-apple-text text-white flex items-center justify-center font-semibold text-sm tracking-tight shadow-apple-subtle">
            A
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-base font-semibold text-apple-text tracking-tight">
                Anki Manager
              </h1>
              <span className="text-xs font-mono text-apple-secondary px-1.5 py-0.5 rounded bg-apple-bg border border-apple-border">
                v2.0
              </span>
            </div>
            <div className="flex items-center gap-1.5 mt-0.5">
              <span
                className={`inline-block w-2 h-2 rounded-full ${
                  isConnected ? 'bg-apple-green' : 'bg-apple-red animate-pulse'
                }`}
              />
              <span className="text-xs text-apple-secondary font-medium">
                {isConnected
                  ? `AnkiConnect v${data?.anki_version ?? '6'} Connected`
                  : 'Anki 연결 끊김 (Anki 실행 필요)'}
              </span>
            </div>
          </div>
        </div>

        {/* Right: Minimal Refresh Action */}
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={onRefresh}
            disabled={isLoading}
            className="inline-flex items-center gap-2 px-3 py-1.5 text-xs font-medium text-apple-text bg-apple-subtle hover:bg-apple-subtleHover rounded-apple-sm border border-apple-border hover:border-apple-borderStrong transition-all shadow-apple-subtle disabled:opacity-40"
            title="대시보드 새로고침"
          >
            <RefreshCw
              className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin text-apple-blue' : 'text-apple-secondary'}`}
            />
            <span>새로고침</span>
          </button>
        </div>
      </div>
    </header>
  )
}
