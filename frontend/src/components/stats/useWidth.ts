import { useEffect, useRef, useState } from 'react'

/** 요소의 현재 너비(px). SVG 차트를 viewBox 늘이기 없이 그리기 위해 쓴다. */
export function useWidth<T extends HTMLElement>(initial = 480) {
  const ref = useRef<T>(null)
  const [width, setWidth] = useState(initial)
  useEffect(() => {
    if (!ref.current) return
    const ro = new ResizeObserver(([entry]) => setWidth(Math.max(240, Math.floor(entry!.contentRect.width))))
    ro.observe(ref.current)
    return () => ro.disconnect()
  }, [])
  return { ref, width }
}
