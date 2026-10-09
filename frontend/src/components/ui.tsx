import type { ReactNode } from 'react'

export function Card({ title, icon, children, right }: { title: string; icon?: ReactNode; children: ReactNode; right?: ReactNode }) {
  return (
    <section className="glass-card p-4">
      <div className="flex items-center justify-between gap-2 mb-3">
        <h3 className="font-heading font-semibold text-sm flex items-center gap-2">
          {icon && <span className="text-accent-strong">{icon}</span>}
          {title}
        </h3>
        {right}
      </div>
      {children}
    </section>
  )
}

export function Segmented<T extends string>({ value, options, onChange, disabled }: {
  value: T
  options: { value: T; label: string; title?: string }[]
  onChange: (v: T) => void
  disabled?: boolean
}) {
  return (
    <div className="flex flex-wrap gap-1 bg-elevated-surface p-1 rounded-full border border-border-brand">
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          title={o.title}
          disabled={disabled}
          onClick={() => onChange(o.value)}
          className={`flex-1 px-2.5 py-1.5 text-xs font-semibold rounded-full whitespace-nowrap transition-colors ${
            value === o.value ? 'bg-accent text-accent-contrast' : 'text-secondary-text hover:text-primary-text hover:bg-surface'
          }`}
        >
          {o.label}
        </button>
      ))}
    </div>
  )
}

export function Slider({ label, value, onChange, hint, disabled, left, right }: {
  label: string
  value: number
  onChange: (v: number) => void
  hint?: string
  disabled?: boolean
  left?: string
  right?: string
}) {
  const pct = Math.round(value * 100)
  return (
    <div className={disabled ? 'opacity-50' : ''}>
      <div className="flex items-center justify-between text-xs mb-1.5">
        <span className="font-semibold text-primary-text">{label}</span>
        <span className="tabular-nums text-accent-strong font-semibold">{pct}%</span>
      </div>
      <input
        type="range"
        min={0}
        max={100}
        step={5}
        value={pct}
        disabled={disabled}
        onChange={(e) => onChange(Number(e.target.value) / 100)}
        className="aiezo-range"
        style={{ ['--pct' as string]: `${pct}%` }}
      />
      {(left || right) && (
        <div className="flex justify-between text-[10px] text-muted-text mt-1">
          <span>{left}</span>
          <span>{right}</span>
        </div>
      )}
      {hint && <p className="text-[11px] text-muted-text mt-1 leading-snug">{hint}</p>}
    </div>
  )
}

export function Toggle({ checked, onChange, label, hint, disabled }: {
  checked: boolean
  onChange: (v: boolean) => void
  label: string
  hint?: ReactNode
  disabled?: boolean
}) {
  return (
    <label className={`flex items-start gap-3 ${disabled ? 'opacity-50' : 'cursor-pointer'}`}>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        disabled={disabled}
        onClick={() => onChange(!checked)}
        className={`mt-0.5 shrink-0 w-9 h-5 rounded-full border transition-colors relative ${
          checked ? 'bg-accent border-transparent' : 'bg-elevated-surface border-border-brand'
        }`}
      >
        <span className={`absolute top-0.5 w-3.5 h-3.5 rounded-full transition-all ${checked ? 'left-[18px] bg-accent-contrast' : 'left-0.5 bg-muted-text'}`} />
      </button>
      <span className="text-xs">
        <span className="font-semibold text-primary-text block">{label}</span>
        {hint && <span className="text-[11px] text-muted-text leading-snug block mt-0.5">{hint}</span>}
      </span>
    </label>
  )
}
