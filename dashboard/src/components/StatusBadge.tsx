import { STATUS_LABELS, type RunStatus } from '../api'

export function StatusBadge({ status }: { status: RunStatus }) {
  return (
    <span className={`badge badge-${status}`}>
      {status === 'running' && <span className="pulse" aria-hidden="true" />}
      {STATUS_LABELS[status] ?? status}
    </span>
  )
}
