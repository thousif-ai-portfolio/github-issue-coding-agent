import { timeAgo, type RunSummary } from '../api'
import { StatusBadge } from './StatusBadge'

interface Props {
  runs: RunSummary[] | null
  selectedId: number | null
  onSelect: (id: number) => void
}

export function RunList({ runs, selectedId, onSelect }: Props) {
  return (
    <section className="panel run-list">
      <h2>Runs</h2>
      {runs === null && <p className="hint">Loading…</p>}
      {runs?.length === 0 && <p className="hint">No runs yet. Start one above.</p>}
      <ul>
        {runs?.map((run) => (
          <li key={run.id}>
            <button
              className={`run-item ${run.id === selectedId ? 'selected' : ''}`}
              aria-current={run.id === selectedId ? 'true' : undefined}
              onClick={() => onSelect(run.id)}
            >
              <span className="run-item-top">
                <span className="run-id">Run {run.id}</span>
                <StatusBadge status={run.status} />
              </span>
              <span className="run-title">
                #{run.issue_number} {run.issue_title || '(fetching issue)'}
              </span>
              <span className="run-meta">
                {run.repo} · {timeAgo(run.created_at)}
              </span>
            </button>
          </li>
        ))}
      </ul>
    </section>
  )
}
