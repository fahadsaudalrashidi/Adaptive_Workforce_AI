interface SortOption<K extends string> {
  key: K
  label: string
}

interface SortToggleProps<K extends string> {
  label: string
  options: SortOption<K>[]
  active: K | 'default'
  onChange: (key: K) => void
  /** Phase 14: 'card' (default) is theme-aware — for the light/dark `.card`
   * tables on the 7 feature pages. 'navy' is for permanently-dark navy-hero
   * sections (e.g. WorkforceCompositionRiver's card-hero, which stays
   * navy-700 regardless of app theme) — using 'card' colors there would put
   * dark-gray text on a dark-navy background in light app mode. */
  variant?: 'card' | 'navy'
}

/**
 * Phase 14 — the exact "Sort: X  Y  Z" control introduced in Phase 13's
 * WorkforceCompositionRiver, extracted so every table across the platform
 * gets the identical interaction (same text-[11px] sizing, same active/
 * inactive color treatment, same motion token) instead of a per-page
 * reimplementation. Pairs with useSortableTable — `active` is expected to
 * be that hook's `sortKey` (including its `'default'` no-sort-applied
 * state, which never matches any option and so never highlights one).
 */
export function SortToggle<K extends string>({ label, options, active, onChange, variant = 'card' }: SortToggleProps<K>) {
  const labelCls = variant === 'navy' ? 'text-navy-400' : 'text-slate-400 dark:text-navy-400'
  const inactiveCls = variant === 'navy'
    ? 'text-navy-300 hover:text-navy-100'
    : 'text-slate-500 dark:text-navy-300 hover:text-slate-800 dark:hover:text-navy-100'
  const activeCls = variant === 'navy'
    ? 'text-blue-400 bg-blue-500/10'
    : 'text-blue-600 dark:text-blue-400 bg-blue-500/10'

  return (
    <div className="flex items-center gap-1 text-[11px]">
      <span className={`${labelCls} me-0.5`}>{label}</span>
      {options.map(opt => (
        <button
          key={opt.key}
          onClick={() => onChange(opt.key)}
          className={`px-1.5 py-0.5 rounded font-medium transition-colors duration-base ease-executive ${
            active === opt.key ? activeCls : inactiveCls
          }`}
        >
          {opt.label}
        </button>
      ))}
    </div>
  )
}
