import { useCallback, useEffect, useRef, useState } from 'react'

// Calls `load` now and then every `intervalMs` while `active`. Runs take minutes and the
// API has no push channel, so the dashboard polls. Returns the latest data, the latest
// error and a function to reload at once (after starting or reviewing a run).
export function usePoll<T>(load: () => Promise<T>, intervalMs: number, active = true) {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<string | null>(null)
  const loadRef = useRef(load)
  useEffect(() => {
    loadRef.current = load
  })

  const reload = useCallback(async () => {
    try {
      setData(await loadRef.current())
      setError(null)
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc))
    }
  }, [])

  useEffect(() => {
    if (!active) return
    void reload()
    const timer = window.setInterval(reload, intervalMs)
    return () => window.clearInterval(timer)
  }, [reload, intervalMs, active])

  return { data, error, reload, setData }
}

// Re-renders every second, for "running for 42 s" labels.
export function useNow(active: boolean): number {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    if (!active) return
    const timer = window.setInterval(() => setNow(Date.now()), 1000)
    return () => window.clearInterval(timer)
  }, [active])
  return now
}
