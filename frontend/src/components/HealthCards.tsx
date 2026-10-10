import React from 'react'
import {
  CheckCircle2,
  AlertTriangle,
  Inbox,
  ArrowRight,
  Flame,
  Palette,
} from 'lucide-react'
import type { DashboardResponse } from '../types/dashboard'

interface HealthCardsProps {
  data: DashboardResponse | null
  onOpenMaintenance: () => void
  onOpenObsidian: () => void
  onOpenDesign: () => void
}

export const HealthCards: React.FC<HealthCardsProps> = ({
  data,
  onOpenMaintenance,
  onOpenObsidian,
  onOpenDesign,
}) => {
  const maintenance = data?.maintenance
  const leechesTotal = data?.leech_total_count ?? 0
  const inbox = data?.obsidian_inbox

  const needsMaintenance = (maintenance?.total_needs_count ?? 0) > 0

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      {/* 1. Maintenance Status Card */}
      <div className="bg-apple-card border border-apple-border rounded-apple p-4 shadow-apple-card flex flex-col justify-between">
        <div className="flex items-start justify-between">
          <div>
            <span className="text-xs font-medium text-apple-secondary uppercase tracking-wider">
              노트 무결성
            </span>
            <div className="flex items-baseline gap-2 mt-1">
              <span className="text-2xl font-bold tracking-tight text-apple-text">
                {needsMaintenance ? maintenance?.total_needs_count : '정상'}
              </span>
              <span className="text-xs text-apple-secondary">
                {needsMaintenance ? '건의 점검 필요' : '모든 필드/오디오 완료'}
              </span>
            </div>
          </div>
          <div
            className={`p-2 rounded-apple-sm ${
              needsMaintenance
                ? 'bg-apple-orange/10 text-apple-orange'
                : 'bg-apple-green/10 text-apple-green'
            }`}
          >
            {needsMaintenance ? (
              <AlertTriangle className="w-4 h-4" />
            ) : (
              <CheckCircle2 className="w-4 h-4" />
            )}
          </div>
        </div>

        <div className="mt-3 pt-3 border-t border-apple-border/60 flex items-center justify-between text-xs">
          <div className="text-apple-secondary font-mono text-[11px]">
            오디오: {maintenance?.missing_audio_count ?? 0} | 뜻: {maintenance?.missing_fields_count ?? 0}
          </div>
          <button
            type="button"
            onClick={onOpenMaintenance}
            className="inline-flex items-center gap-1 font-medium text-apple-blue hover:text-apple-blueHover transition-colors"
          >
            <span>정리하기</span>
            <ArrowRight className="w-3 h-3" />
          </button>
        </div>
      </div>

      {/* 2. Obsidian Inbox Card */}
      <div className="bg-apple-card border border-apple-border rounded-apple p-4 shadow-apple-card flex flex-col justify-between">
        <div className="flex items-start justify-between">
          <div>
            <span className="text-xs font-medium text-apple-secondary uppercase tracking-wider">
              Obsidian Inbox
            </span>
            <div className="flex items-baseline gap-2 mt-1">
              <span className="text-2xl font-bold tracking-tight text-apple-text">
                {inbox?.total_count ?? 0}
              </span>
              <span className="text-xs text-apple-secondary font-medium">
                개 대기 (단어 {inbox?.vocab_count ?? 0} · 문장 {inbox?.sentence_count ?? 0})
              </span>
            </div>
          </div>
          <div className="p-2 rounded-apple-sm bg-apple-blue/10 text-apple-blue">
            <Inbox className="w-4 h-4" />
          </div>
        </div>

        <div className="mt-3 pt-3 border-t border-apple-border/60 flex items-center justify-between text-xs">
          <span className="text-apple-secondary text-[11px]">
            {inbox?.available ? '수집함 연동 정상' : 'Inbox 파일 없음'}
          </span>
          <button
            type="button"
            onClick={onOpenObsidian}
            disabled={!inbox?.available || (inbox?.total_count ?? 0) === 0}
            className="inline-flex items-center gap-1 font-medium text-apple-blue hover:text-apple-blueHover disabled:opacity-40 transition-colors"
          >
            <span>가져오기</span>
            <ArrowRight className="w-3 h-3" />
          </button>
        </div>
      </div>

      {/* 3. Card Template & Design Management Card */}
      <div className="bg-apple-card border border-apple-border rounded-apple p-4 shadow-apple-card flex flex-col justify-between">
        <div className="flex items-start justify-between">
          <div>
            <span className="text-xs font-medium text-apple-secondary uppercase tracking-wider">
              카드 템플릿 관리
            </span>
            <div className="flex items-baseline gap-2 mt-1">
              <span className="text-2xl font-bold tracking-tight text-apple-text font-mono">
                v2.0
              </span>
              <span className="text-xs text-apple-secondary">
                Cloze Context 적용됨
              </span>
            </div>
          </div>
          <div className="p-2 rounded-apple-sm bg-apple-purple/10 text-purple-400">
            <Palette className="w-4 h-4" />
          </div>
        </div>

        <div className="mt-3 pt-3 border-t border-apple-border/60 flex items-center justify-between text-xs">
          <span className="text-apple-secondary text-[11px]">
            Card 1/2 백업 및 복원
          </span>
          <button
            type="button"
            onClick={onOpenDesign}
            className="inline-flex items-center gap-1 font-medium text-apple-blue hover:text-apple-blueHover transition-colors"
          >
            <span>디자인 관리</span>
            <ArrowRight className="w-3 h-3" />
          </button>
        </div>
      </div>

      {/* 4. Chronic Leech Card */}
      <div className="bg-apple-card border border-apple-border rounded-apple p-4 shadow-apple-card flex flex-col justify-between">
        <div className="flex items-start justify-between">
          <div>
            <span className="text-xs font-medium text-apple-secondary uppercase tracking-wider">
              만성 오답 (Leech)
            </span>
            <div className="flex items-baseline gap-2 mt-1">
              <span className="text-2xl font-bold tracking-tight text-apple-red font-mono">
                {leechesTotal.toLocaleString()}
              </span>
              <span className="text-xs text-apple-secondary">장</span>
              <span className="text-xs text-apple-secondary">
                Lapse ≥ 4회 또는 Ease ≤ 130%
              </span>
            </div>
          </div>
          <div className="p-2 rounded-apple-sm bg-apple-red/10 text-apple-red">
            <Flame className="w-4 h-4" />
          </div>
        </div>

        <div className="mt-3 pt-3 border-t border-apple-border/60 flex items-center justify-between text-xs">
          <span className="text-apple-secondary text-[11px]">
            하단 인스펙터 분석
          </span>
          <span className="font-mono text-apple-secondary text-[11px]">
            상위 8개 검토
          </span>
        </div>
      </div>
    </div>
  )
}
