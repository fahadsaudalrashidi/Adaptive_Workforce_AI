import { useMemo, useState } from 'react'

/**
 * Phase 40 — generic client-side employee/ID search-filter, extracted so
 * every per-employee table across the platform (Gratuity, WPS, Leave
 * Balance, GOSI, Contract Expiry, Succession Readiness) shares ONE search
 * implementation instead of reimplementing the same
 * `!query || fields.some(v => v.includes(query))` matching logic per page
 * (the pattern EmployeeRiskDashboard.tsx built ad hoc in Phase 13/31 for
 * its own, considerably more elaborate multi-filter search — that page
 * already has a working, more complex system of its own and is left as-is;
 * this hook is for the pages that had NO search at all).
 *
 * Case-insensitive substring match across whichever fields the caller
 * supplies via `getSearchableFields` — typically the employee ID (real or
 * hashed, whichever this page actually displays after the Phase 40
 * record_id_safe-vs-real-ID decision — see PHASE_27_EOS_RECONCILIATION_GOSI_AUDIT_SEARCH_REPORT.md
 * §3) and, where shown, the employee name. Matches what's actually on
 * screen, not hidden data the user can't see and wouldn't think to search.
 */
export function useEmployeeSearch<T>(
  rows: T[],
  getSearchableFields: (row: T) => (string | null | undefined)[],
) {
  const [query, setQuery] = useState('')

  const filteredRows = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!q) return rows
    return rows.filter(row =>
      getSearchableFields(row).some(field => field?.toLowerCase().includes(q))
    )
  }, [rows, query, getSearchableFields])

  return { query, setQuery, filteredRows }
}
