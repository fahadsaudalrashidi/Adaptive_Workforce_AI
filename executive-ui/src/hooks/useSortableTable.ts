import { useMemo, useState } from 'react'

/**
 * Phase 14 — generic client-side table/list sort, extracted from the
 * pattern built ad hoc in WorkforceCompositionRiver.tsx (Phase 13).
 *
 * Bakes in the fix for a real bug caught in Phase 13: the first version of
 * that component defaulted to an ACTIVE sort key, which silently re-ordered
 * the list on load relative to whatever order the parent had already
 * computed — a violation of "keep the exact same default state." This hook
 * always starts at `'default'`, which returns `data` in its original prop
 * order, untouched. Sorting only ever happens after the caller's own UI
 * invokes `setSortKey` with one of the real keys — i.e. after a user
 * click, never automatically.
 *
 * Generic over any row shape and any set of named sort comparators, so it
 * can be reused for department tables, employee tables, funnel/source
 * tables, etc. without each page re-deriving the same default-order bug
 * class from scratch.
 */
export function useSortableTable<T, K extends string>(
  data: T[],
  comparators: Record<K, (a: T, b: T) => number>,
) {
  const [sortKey, setSortKey] = useState<K | 'default'>('default')

  const sorted = useMemo(() => {
    if (sortKey === 'default') return data
    const cmp = comparators[sortKey]
    return cmp ? [...data].sort(cmp) : data
  }, [data, sortKey, comparators])

  return { sorted, sortKey, setSortKey }
}
