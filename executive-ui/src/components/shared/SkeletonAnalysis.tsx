/**
 * Phase 11 — shape-matched skeleton loading state, replacing the
 * spinner-only "Analyzing…" boxes used across every upload page. Mirrors
 * the eventual KPI-grid + narrative + table layout so the page feels fast
 * and considered during real analysis latency, not stalled.
 */
export function SkeletonAnalysis({ kpiCount = 4 }: { kpiCount?: number }) {
  return (
    <div className="space-y-5" aria-busy="true" aria-label="Loading analysis">
      {/* Fixed literal classes (not a template-literal count) — Tailwind's
          JIT scanner only picks up class names that appear verbatim in
          source, so a dynamic `grid-cols-${n}` would silently compile to
          nothing. */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {Array.from({ length: kpiCount }).map((_, i) => (
          <div key={i} className="card p-5 space-y-3">
            <div className="skeleton h-3 w-2/3" />
            <div className="skeleton h-7 w-1/2" />
            <div className="skeleton h-2.5 w-1/3" />
          </div>
        ))}
      </div>

      <div className="card p-4 space-y-2">
        <div className="skeleton h-3 w-full" />
        <div className="skeleton h-3 w-5/6" />
      </div>

      <div className="card p-4">
        <div className="skeleton h-4 w-40 mb-4" />
        <div className="space-y-2.5">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="flex items-center gap-4">
              <div className="skeleton h-3 w-28" />
              <div className="skeleton h-3 flex-1" />
              <div className="skeleton h-3 w-12" />
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
