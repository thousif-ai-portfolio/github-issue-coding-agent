import { useEffect, useState } from 'react'
import { api } from './api'
import { NewRun } from './components/NewRun'
import { RunDetail } from './components/RunDetail'
import { RunList } from './components/RunList'
import { usePoll } from './usePoll'

// The selected run lives in the URL (#/runs/6), so a run can be linked and survives reload.
function readHash(): number | null {
  const match = window.location.hash.match(/^#\/runs\/(\d+)$/)
  return match ? Number(match[1]) : null
}

export default function App() {
  const [selectedId, setSelectedId] = useState<number | null>(readHash)
  const runs = usePoll(api.runs, 5000)
  const health = usePoll(api.health, 30000)

  useEffect(() => {
    const onHash = () => setSelectedId(readHash())
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [])

  // With nothing selected, show the newest run.
  const shownId = selectedId ?? runs.data?.[0]?.id ?? null

  function select(id: number) {
    window.location.hash = `#/runs/${id}`
  }

  async function started(id: number) {
    await runs.reload()
    select(id)
  }

  const counts = runs.data?.reduce<Record<string, number>>((acc, run) => {
    acc[run.status] = (acc[run.status] ?? 0) + 1
    return acc
  }, {})

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <span className="logo" aria-hidden="true">{'{ }'}</span>
          <div>
            <h1>Issue Coding Agent</h1>
            <p>Reads an issue, writes a failing test, fixes it, waits for your review.</p>
          </div>
        </div>
        <div className="topbar-meta">
          {counts?.awaiting_approval ? (
            <span className="pill attention">{counts.awaiting_approval} awaiting review</span>
          ) : null}
          {counts?.running ? <span className="pill">{counts.running} running</span> : null}
          <span className={`pill ${health.error ? 'offline' : 'online'}`}>
            {health.error ? 'API offline' : health.data ? `API · ${health.data.model}` : 'API…'}
          </span>
        </div>
      </header>

      {runs.error && !runs.data && (
        <p className="callout danger banner">
          Cannot reach the API ({runs.error}). Start it with <code>uvicorn agent.main:app</code>.
        </p>
      )}

      <main className="layout">
        <aside className="sidebar">
          <NewRun onStarted={started} />
          <RunList runs={runs.data} selectedId={shownId} onSelect={select} />
        </aside>
        {shownId !== null ? (
          <RunDetail key={shownId} runId={shownId} onChanged={runs.reload} />
        ) : (
          <section className="panel detail empty">
            <h2>No run selected</h2>
            <p className="hint">Pick a demo issue and start a run. Steps appear here as the agent works.</p>
          </section>
        )}
      </main>
    </div>
  )
}
