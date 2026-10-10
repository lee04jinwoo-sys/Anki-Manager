import React, { useCallback, useState } from 'react'

interface TipState {
  x: number
  y: number
  content: React.ReactNode
}

/** 마우스 위치를 따라가는 툴팁. show(e, content) / hide() */
export function useTooltip() {
  const [tip, setTip] = useState<TipState | null>(null)
  const show = useCallback((e: React.MouseEvent, content: React.ReactNode) => {
    setTip({ x: e.clientX, y: e.clientY, content })
  }, [])
  const hide = useCallback(() => setTip(null), [])
  const node = tip ? (
    <div
      role="tooltip"
      className="pointer-events-none fixed z-50 rounded-apple-sm border border-apple-borderStrong bg-apple-bg/95 px-2.5 py-1.5 text-[11px] leading-relaxed text-apple-text shadow-apple-modal"
      style={{ left: Math.min(tip.x + 12, window.innerWidth - 220), top: tip.y + 14 }}
    >
      {tip.content}
    </div>
  ) : null
  return { node, show, hide }
}
