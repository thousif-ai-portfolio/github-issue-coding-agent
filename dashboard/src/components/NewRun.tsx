import { useEffect, useState, type FormEvent } from 'react'
import { api, type Issue, type Source } from '../api'

// Picks an open issue from the demo repo or a GitHub repository and starts a run on it.
export function NewRun({ onStarted }: { onStarted: (runId: number) => void }) {
  const [source, setSource] = useState<Source>('demo')
  const [repo, setRepo] = useState('')
  const [issues, setIssues] = useState<Issue[]>([])
  const [issueNumber, setIssueNumber] = useState<number | null>(null)
  const [loading, setLoading] = useState(true) // the demo issues load on mount
  const [starting, setStarting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function loadIssues(from: Source, name: string) {
    setLoading(true)
    setError(null)
    setIssues([])
    setIssueNumber(null)
    try {
      const found = await api.issues(from, from === 'github' ? name : undefined)
      setIssues(found)
      setIssueNumber(found[0]?.number ?? null)
      if (found.length === 0) setError('No open issues.')
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    api
      .issues('demo')
      .then((found) => {
        setIssues(found)
        setIssueNumber(found[0]?.number ?? null)
      })
      .catch((exc: Error) => setError(exc.message))
      .finally(() => setLoading(false))
  }, [])

  function chooseSource(value: Source) {
    setSource(value)
    if (value === 'demo') void loadIssues('demo', '')
    else {
      setIssues([])
      setIssueNumber(null)
      setError(null)
    }
  }

  async function start(event: FormEvent) {
    event.preventDefault()
    if (issueNumber === null) return
    setStarting(true)
    setError(null)
    try {
      const run = await api.startRun(source, issueNumber, source === 'github' ? repo : undefined)
      onStarted(run.id)
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc))
    } finally {
      setStarting(false)
    }
  }

  const selected = issues.find((issue) => issue.number === issueNumber)

  return (
    <form className="panel new-run" onSubmit={start}>
      <h2>New run</h2>
      <div className="segmented" role="radiogroup" aria-label="Issue source">
        {(['demo', 'github'] as const).map((value) => (
          <button
            key={value}
            type="button"
            role="radio"
            aria-checked={source === value}
            className={source === value ? 'active' : ''}
            onClick={() => chooseSource(value)}
          >
            {value === 'demo' ? 'Demo repo' : 'GitHub'}
          </button>
        ))}
      </div>

      {source === 'github' && (
        <div className="row">
          <input
            aria-label="Repository"
            placeholder="owner/name"
            value={repo}
            onChange={(e) => {
              // The loaded issues belong to the old name; a run must not mix the two.
              setRepo(e.target.value.trim())
              setIssues([])
              setIssueNumber(null)
            }}
          />
          <button
            type="button"
            className="secondary"
            disabled={!repo || loading}
            onClick={() => loadIssues('github', repo)}
          >
            Load
          </button>
        </div>
      )}

      <select
        aria-label="Issue"
        value={issueNumber ?? ''}
        disabled={issues.length === 0}
        onChange={(e) => setIssueNumber(Number(e.target.value))}
      >
        {issues.length === 0 && <option value="">{loading ? 'Loading issues…' : 'No issues loaded'}</option>}
        {issues.map((issue) => (
          <option key={issue.number} value={issue.number}>
            #{issue.number} {issue.title}
          </option>
        ))}
      </select>

      {selected?.body && <p className="issue-body">{selected.body}</p>}
      {error && <p className="error">{error}</p>}

      <button type="submit" disabled={issueNumber === null || starting}>
        {starting ? 'Starting…' : 'Start run'}
      </button>
      <p className="hint">A run takes a few minutes on a laptop CPU.</p>
    </form>
  )
}
