import type { ReactNode } from 'react'

/**
 * Phase 15 — real-screenshot review confirmed Latin-script content inside
 * Arabic RTL tables (employee IDs like "EMP-C825B3", English department
 * names, etc.) had inconsistent internal alignment: some cells' Latin
 * content started from the right, some from the left, causing visual
 * "stumbling" while reading down a column. Root cause: the browser's
 * bidi algorithm resolves each cell's start-edge independently based on
 * its first strong-direction character, so a cell starting with a digit
 * or Latin letter can render LTR-anchored while its RTL-context neighbor
 * renders RTL-anchored, even with identical CSS.
 *
 * Fix: wrap any Latin-script table value (IDs, English names inside an
 * Arabic table, numbers-as-text) in this component, which pins `dir="ltr"`
 * and `unicode-bidi: isolate` uniformly — so every such cell resolves its
 * internal direction identically regardless of what page it's on. Use
 * this instead of ad hoc per-instance `dir="ltr"` spans.
 */
export function LatinText({ children, className = '' }: { children: ReactNode; className?: string }) {
  return (
    <span dir="ltr" style={{ unicodeBidi: 'isolate' }} className={className}>
      {children}
    </span>
  )
}
