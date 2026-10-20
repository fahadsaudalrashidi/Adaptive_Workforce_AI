import { Search, X } from 'lucide-react'

interface EmployeeSearchInputProps {
  value: string
  onChange: (value: string) => void
  placeholder: string
  resultCount?: number
  totalCount?: number
}

/**
 * Phase 40 — the ONE search-box UI every per-employee table should render
 * through, paired with `useEmployeeSearch`. Styling matches the search
 * input EmployeeRiskDashboard.tsx already established (same icon, size,
 * border, focus ring) so this reads as the same platform pattern rather
 * than a new one-off control.
 */
export function EmployeeSearchInput({ value, onChange, placeholder, resultCount, totalCount }: EmployeeSearchInputProps) {
  return (
    <div className="flex items-center gap-2">
      <div className="relative flex-1 min-w-[180px] max-w-xs">
        <Search size={13} className="absolute left-2.5 rtl:left-auto rtl:right-2.5 top-1/2 -translate-y-1/2 text-slate-400" />
        <input
          type="text"
          value={value}
          onChange={e => onChange(e.target.value)}
          placeholder={placeholder}
          className="w-full pl-7 pr-7 rtl:pr-7 rtl:pl-7 py-1.5 text-xs rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-200 focus:outline-none focus:border-blue-400"
        />
        {value && (
          <button
            onClick={() => onChange('')}
            className="absolute right-2 rtl:right-auto rtl:left-2 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 dark:hover:text-slate-300"
            aria-label="Clear search"
          >
            <X size={12} />
          </button>
        )}
      </div>
      {value && resultCount !== undefined && totalCount !== undefined && (
        <span className="text-[11px] text-slate-400 dark:text-slate-500 whitespace-nowrap">
          {resultCount} / {totalCount}
        </span>
      )}
    </div>
  )
}
