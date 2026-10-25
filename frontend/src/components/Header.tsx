import React from 'react'
import { Inbox, Palette, RefreshCw, Wrench } from 'lucide-react'
import type { DashboardResponse } from '../types/dashboard'
import { showObsidianImport } from '../lib/obsidianInbox'

interface HeaderProps {
  data: DashboardResponse | null
  isLoading: boolean
  activeLanguage: 'en' | 'zh'
  onLanguageChange: (lang: 'en' | 'zh') => void
  onRefresh: () => void
  onOpenMaintenance: () => void
  onOpenObsidian: () => void
  onOpenDesign: () => void
}

const ActionButton: React.FC<{
  icon: React.ReactNode
  label: string
  badge?: number
  onClick: () => void
  disabled?: boolean
  title?: string
}> = ({ icon, label, badge, onClick, disabled, title }) => (
  <button
    type="button"
    onClick={onClick}
    disabled={disabled}
    title={title}
    className="inline-flex items-center gap-1.5 rounded-apple-sm border border-apple-border bg-apple-subtle px-3 py-1.5 text-xs font-medium text-apple-text transition-colors hover:border-apple-borderStrong hover:bg-apple-subtleHover disabled:opacity-40"
  >
    {icon}
    <span>{label}</span>
    {badge !== undefined && badge > 0 && (
      <span className="rounded-full bg-apple-blue px-1.5 text-[10px] font-semibold leading-4 text-white">{badge}</span>
    )}
  </button>
)

export const Header: React.FC<HeaderProps> = ({
  data,
  isLoading,
  activeLanguage,
  onLanguageChange,
  onRefresh,
  onOpenMaintenance,
  onOpenObsidian,
  onOpenDesign,
}) => {
  const isConnected = data?.connected ?? false
  const inbox = data?.obsidian_inbox
  const needs = data?.maintenance?.total_needs_count ?? 0

  return (
    <header className="sticky top-0 z-30 border-b border-apple-border bg-apple-card/80 px-6 py-3 backdrop-blur-md">
      <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <h1 className="text-base font-semibold tracking-tight text-apple-text">Anki Manager</h1>
          <span className="inline-flex items-center gap-1.5 text-xs text-apple-secondary">
            <span className={`inline-block h-2 w-2 rounded-full ${isConnected ? 'bg-apple-green' : 'animate-pulse bg-apple-red'}`} />
            {isConnected ? 'Anki 연결됨' : 'Anki 연결 끊김'}
          </span>

          {/* Apple-style Language Segmented Switch */}
          <div className="ml-2 inline-flex items-center rounded-apple-sm bg-apple-subtle p-0.5 border border-apple-border text-xs">
            <button
              type="button"
              onClick={() => onLanguageChange('en')}
              className={`px-2.5 py-1 rounded-[6px] font-medium transition-all ${
                activeLanguage === 'en'
                  ? 'bg-white text-apple-text shadow-sm dark:bg-apple-card font-semibold'
                  : 'text-apple-secondary hover:text-apple-text'
              }`}
            >
              🇺🇸 English
            </button>
            <button
              type="button"
              onClick={() => onLanguageChange('zh')}
              className={`px-2.5 py-1 rounded-[6px] font-medium transition-all ${
                activeLanguage === 'zh'
                  ? 'bg-white text-apple-text shadow-sm dark:bg-apple-card font-semibold'
                  : 'text-apple-secondary hover:text-apple-text'
              }`}
            >
              🇨🇳 中文
            </button>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {showObsidianImport(inbox) && (
            <ActionButton
              icon={<Inbox className="h-3.5 w-3.5 text-apple-secondary" />}
              label="가져오기"
              badge={inbox?.total_count}
              onClick={onOpenObsidian}
              disabled={!isConnected}
              title="Obsidian Inbox 항목을 Anki 카드로 등록"
            />
          )}
          <ActionButton
            icon={<Wrench className="h-3.5 w-3.5 text-apple-secondary" />}
            label="노트 정리"
            badge={needs}
            onClick={onOpenMaintenance}
            disabled={!isConnected}
            title={needs > 0 ? `오디오·뜻 누락 ${needs}개` : '빈 필드·오디오·덱 이동·중복 정리'}
          />
          <ActionButton
            icon={<Palette className="h-3.5 w-3.5 text-apple-secondary" />}
            label="디자인"
            onClick={onOpenDesign}
            disabled={!isConnected}
            title="카드 템플릿·CSS 백업/복원"
          />
          <button
            type="button"
            onClick={onRefresh}
            disabled={isLoading}
            title="새로고침"
            className="rounded-apple-sm border border-apple-border p-1.5 text-apple-secondary hover:bg-apple-subtle disabled:opacity-40"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${isLoading ? 'animate-spin text-apple-blue' : ''}`} />
          </button>
        </div>
      </div>
    </header>
  )
}
