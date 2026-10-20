import { useEffect, useRef, useState } from 'react'

/**
 * Animates a number from 0 (or its previous value) up to `target` over
 * `durationMs`, using requestAnimationFrame with an ease-out curve —
 * Phase 11's "hero numbers deserve more than a static box" treatment.
 * Respects prefers-reduced-motion (jumps straight to target, no animation).
 */
export function useCountUp(target: number, durationMs = 900): number {
  const [value, setValue] = useState(target)
  const prevTarget = useRef(target)
  const frameRef = useRef<number>()

  useEffect(() => {
    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    if (reduceMotion || !Number.isFinite(target)) {
      setValue(target)
      prevTarget.current = target
      return
    }

    const from = prevTarget.current
    const to = target
    if (from === to) return

    const start = performance.now()
    const easeOutCubic = (t: number) => 1 - Math.pow(1 - t, 3)

    function tick(now: number) {
      const elapsed = now - start
      const progress = Math.min(1, elapsed / durationMs)
      const eased = easeOutCubic(progress)
      setValue(from + (to - from) * eased)
      if (progress < 1) {
        frameRef.current = requestAnimationFrame(tick)
      } else {
        prevTarget.current = to
      }
    }
    frameRef.current = requestAnimationFrame(tick)

    return () => {
      if (frameRef.current) cancelAnimationFrame(frameRef.current)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [target, durationMs])

  return value
}
