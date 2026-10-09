import React, { useEffect, useState, useCallback } from 'react'
import { Header } from './components/Header'
import { HealthCards } from './components/HealthCards'
import { DeckGrid } from './components/DeckGrid'
import { LinkManagerPanel } from './components/LinkManagerPanel'
import { JobDrawer } from './components/JobDrawer'
import { MaintenanceModal } from './components/modals/MaintenanceModal'
import { ObsidianModal } from './components/modals/ObsidianModal'
import { DesignModal } from './components/modals/DesignModal'
import type { DashboardResponse, JobState } from './types/dashboard'
import { api } from './api/client'
import { Loader2, AlertCircle } from 'lucide-react'

export const App: React.FC = () => {
  const [data, setData] = useState<DashboardResponse | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Active Job State (synced dynamically)
  const [jobState, setJobState] = useState<JobState>({
    is_running: false,
    source: '',
    progress: 0,
    current_step: '대기 중',
    status: 'idle',
    logs: [],
    meta: {},
    candidates: { sentences: [], vocab: [] },
  })

  // Modals state
  const [isMaintenanceOpen, setIsMaintenanceOpen] = useState(false)
  const [isObsidianOpen, setIsObsidianOpen] = useState(false)
  const [isDesignOpen, setIsDesignOpen] = useState(false)

  const loadDashboard = useCallback(async (isInitial = false) => {
    if (isInitial) setIsLoading(true)
    setError(null)
    try {
      const res = await api.getDashboard()
      setData(res)
      if (res.active_job) {
        setJobState(res.active_job)
      }
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : '대시보드 데이터를 불러오지 못했습니다.',
      )
    } finally {
      if (isInitial) setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    loadDashboard(true)
  }, [loadDashboard])

  // Polling for active background jobs
  useEffect(() => {
    const isJobActive = jobState.is_running || jobState.status === 'running'
    const intervalTime = isJobActive ? 1500 : 15000

    const timer = setInterval(async () => {
      try {
        const currentJob = await api.getJobState()
        setJobState(currentJob)

        // When a running job finishes, refresh dashboard data
        if (
          isJobActive &&
          !currentJob.is_running &&
          (currentJob.status === 'success' || currentJob.status === 'error')
        ) {
          loadDashboard(false)
        }
      } catch (e) {
        console.error('Job polling error:', e)
      }
    }, intervalTime)

    return () => clearInterval(timer)
  }, [jobState.is_running, jobState.status, loadDashboard])

  return (
    <div className="min-h-screen bg-apple-bg flex flex-col font-sans">
      {/* 1. Sticky Header Bar */}
      <Header
        data={data}
        isLoading={isLoading}
        onRefresh={() => loadDashboard(false)}
      />

      {/* Main Content Area */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-6 py-6 space-y-6">
        {/* Error Banner */}
        {error && (
          <div className="p-4 rounded-apple bg-apple-red/10 border border-apple-red/20 text-xs text-apple-red flex items-start gap-3 shadow-apple-subtle">
            <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
            <div>
              <span className="font-semibold">오류 발생:</span> {error}
            </div>
          </div>
        )}

        {/* Offline / Connection Error Banner */}
        {data && !data.connected && (
          <div className="p-4 rounded-apple bg-apple-red/10 border border-apple-red/20 text-xs text-apple-red flex items-start gap-3 shadow-apple-subtle">
            <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
            <div>
              <span className="font-semibold">Anki 실행 필요:</span> Anki 데스크톱 앱이 실행 중이지 않거나 AnkiConnect 애드온(포트 8765)이 활성화되지 않았습니다. Anki 앱을 실행한 후 상단 새로고침 버튼을 눌러주세요.
            </div>
          </div>
        )}

        {/* Global Loading Spinner */}
        {isLoading && !data ? (
          <div className="py-32 flex flex-col items-center justify-center text-apple-secondary text-xs">
            <Loader2 className="w-8 h-8 animate-spin text-apple-blue mb-3" />
            <span>Anki 데이터 및 통계 로드 중...</span>
          </div>
        ) : (
          <>
            {/* 2. Top Summary Health Metrics Cards */}
            <HealthCards
              data={data}
              onOpenMaintenance={() => setIsMaintenanceOpen(true)}
              onOpenObsidian={() => setIsObsidianOpen(true)}
              onOpenDesign={() => setIsDesignOpen(true)}
            />

            {/* 3. Deck Review Status Grid */}
            <DeckGrid decks={data?.decks ?? []} />

            {/* 4. Unified Vocab Context & Leech Studio */}
            <LinkManagerPanel onRefreshDashboard={() => loadDashboard(false)} />
          </>
        )}
      </main>

      {/* 5. Live Background Task Drawer & Log Monitor */}
      <JobDrawer
        job={jobState}
        onCancelSuccess={() => loadDashboard(false)}
      />

      {/* Modals */}
      <MaintenanceModal
        isOpen={isMaintenanceOpen}
        onClose={() => setIsMaintenanceOpen(false)}
        onStarted={() => {
          loadDashboard(false)
        }}
      />

      <ObsidianModal
        isOpen={isObsidianOpen}
        onClose={() => setIsObsidianOpen(false)}
        onStarted={() => {
          loadDashboard(false)
        }}
      />

      <DesignModal
        isOpen={isDesignOpen}
        onClose={() => setIsDesignOpen(false)}
        onStarted={() => {
          loadDashboard(false)
        }}
      />
    </div>
  )
}
