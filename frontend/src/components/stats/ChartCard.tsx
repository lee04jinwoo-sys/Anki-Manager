import React, { useState } from 'react'

/** 차트 카드: 제목·설명·범례 + "표로 보기" 전환 */
export const ChartCard: React.FC<{
  title: string
  subtitle: string
  legend?: React.ReactNode
  controls?: React.ReactNode
  table: React.ReactNode
  children: React.ReactNode
}> = ({ title, subtitle, legend, controls, table, children }) => {
  const [showTable, setShowTable] = useState(false)
  return (
    <section className="flex flex-col rounded-apple border border-apple-border bg-apple-card p-5 shadow-apple-card">
      <div className="mb-3 flex items-start justify-between gap-2">
        <div>
          <h2 className="text-sm font-semibold text-apple-text">{title}</h2>
          <p className="text-xs text-apple-secondary">{subtitle}</p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          {controls}
          <button
            type="button"
            onClick={() => setShowTable((v) => !v)}
            className="rounded-apple-sm border border-apple-border px-2 py-1 text-xs text-apple-secondary hover:bg-apple-subtle"
          >
            {showTable ? '차트' : '표'}
          </button>
        </div>
      </div>
      {legend && !showTable && <div className="mb-2 flex flex-wrap gap-3 text-[11px] text-apple-secondary">{legend}</div>}
      <div className="flex-1">{showTable ? table : children}</div>
    </section>
  )
}

export const LegendSwatch: React.FC<{ color: string; label: string; line?: boolean }> = ({ color, label, line }) => (
  <span className="inline-flex items-center gap-1.5">
    <span
      className="inline-block rounded-full"
      style={{ background: color, width: line ? 14 : 9, height: line ? 2 : 9 }}
    />
    {label}
  </span>
)

export const SimpleTable: React.FC<{ head: string[]; rows: (string | number)[][] }> = ({ head, rows }) => (
  <table className="w-full text-left text-xs">
    <thead className="text-apple-secondary">
      <tr>
        {head.map((h, i) => (
          <th key={h} className={`py-1 font-medium ${i > 0 ? 'text-right' : ''}`}>
            {h}
          </th>
        ))}
      </tr>
    </thead>
    <tbody className="font-mono text-apple-text">
      {rows.map((r) => (
        <tr key={String(r[0])} className="border-t border-apple-border">
          {r.map((c, i) => (
            <td key={i} className={`py-1 ${i > 0 ? 'text-right' : ''}`}>
              {typeof c === 'number' ? c.toLocaleString() : c}
            </td>
          ))}
        </tr>
      ))}
    </tbody>
  </table>
)

/** 기간 선택 (세그먼트 버튼) */
export function RangeToggle<T extends string>({ value, options, onChange }: { value: T; options: { value: T; label: string }[]; onChange: (v: T) => void }) {
  return (
    <div className="inline-flex rounded-apple-sm border border-apple-border p-0.5 text-[11px]">
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          onClick={() => onChange(o.value)}
          className={`rounded px-2 py-0.5 ${value === o.value ? 'bg-apple-subtleHover text-apple-text' : 'text-apple-secondary hover:text-apple-text'}`}
        >
          {o.label}
        </button>
      ))}
    </div>
  )
}
