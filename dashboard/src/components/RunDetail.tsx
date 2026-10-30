import { useState } from 'react'
import { api, formatDuration, parseTime, STEP_LABELS, type RunDetail as Run, type Step } from '../api'
import { useNow, usePoll } from '../usePoll'
import { Diff } from './Diff'
import { StatusBadge } from './StatusBadge'

interface Props {
  runId: number
  onChanged: () => void
}

export function RunDetail({ runId, onChanged }: Props) {
  const [polling, setPolling] = useState(true)
  const { data: run, error, reload } = usePoll(
    async () => {
      const loaded = await api.run(runId)
      // Only a running run changes on its own; stop polling once it settles.
      setPolling(loaded.status === 'running')
      return loaded
    },
    3000,
    polling,
  )
  const now = useNow(run?.status === 'running')

  if (error && !run) return <section className="panel detail"><p className="error">{error}</p></section>
  if (!run || run.id !== runId) return <section className="panel detail"><p className="hint">Loading run {runId}…</p></section>

  // Time the agent spent working, not time spent waiting for a reviewer.
  const running = run.status === 'running'
  const agentMs = running
    ? now - parseTime(run.created_at).getTime()
    : run.steps.filter((s) => s.name !== 'human_review').reduce((sum, s) => sum + s.duration_ms, 0)

  async function afterReview() {
    setPolling(true)
    await reload()
    onChanged()
  }

  return (
    <section className="panel detail">
      <header className="detail-header">
        <div>
          <p className="eyebrow">
            Run {run.id} · {run.repo} · issue #{run.issue_number}
          </p>
          <h2>{run.issue_title || 'Fetching issue…'}</h2>
          <p className="run-meta">
            {run.model} · {running ? 'running for ' : 'agent time '}
            {formatDuration(Math.max(0, agentMs))}
          </p>
        </div>
        <StatusBadge status={run.status} />
      </header>

      {run.status === 'awaiting_approval' && <ReviewBox run={run} onDone={afterReview} />}
      <Outcome run={run} />

      {run.diff && (
        <Section title="Proposed fix">
          {run.explanation && <p className="explanation">{run.explanation}</p>}
          <Diff diff={run.diff} />
        </Section>
      )}
      {run.regression_test && (
        <Section title="Regression test" note="Written by the agent; it failed before the fix.">
          <pre className="code">{run.regression_test}</pre>
        </Section>
      )}
      {run.test_output && (
        <Section title="Sandbox test output">
          <pre className="code">{run.test_output}</pre>
        </Section>
      )}

      <Section title="Steps" note={`${run.steps.length} recorded`}>
        <Timeline steps={run.steps} running={run.status === 'running'} now={now} startedAt={run.created_at} />
      </Section>
    </section>
  )
}

function Section({ title, note, children }: { title: string; note?: string; children: React.ReactNode }) {
  return (
    <div className="section">
      <h3>
        {title}
        {note && <span className="note">{note}</span>}
      </h3>
      {children}
    </div>
  )
}

function Outcome({ run }: { run: Run }) {
  if (run.status === 'pr_opened' && run.pr_url)
    return (
      <p className="callout success">
        Draft pull request opened: <a href={run.pr_url} target="_blank" rel="noreferrer">{run.pr_url}</a>
      </p>
    )
  if (run.status === 'approved')
    return <p className="callout success">Approved. The demo repo has no GitHub remote, so the patch was saved to data/patches/run-{run.id}.diff.</p>
  if (run.status === 'rejected')
    return <p className="callout muted">Rejected{run.error ? `: ${run.error}` : '.'}</p>
  if (run.status === 'skipped')
    return <p className="callout muted">Skipped, not a bug or feature request{run.explanation ? `: ${run.explanation}` : '.'}</p>
  if (run.status === 'failed')
    return <p className="callout danger">Failed{run.error ? `: ${run.error}` : '.'}</p>
  return null
}

function ReviewBox({ run, onDone }: { run: Run; onDone: () => Promise<void> }) {
  const [comment, setComment] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const isDemo = run.repo === 'demo'

  async function review(approved: boolean) {
    setBusy(true)
    setError(null)
    try {
      await api.review(run.id, approved, comment)
      await onDone()
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc))
      setBusy(false)
    }
  }

  return (
    <div className="review">
      <div>
        <h3>Review needed</h3>
        <p>
          The tests passed in the sandbox. Approving {isDemo ? 'saves the patch' : `opens a draft pull request on ${run.repo}`}.
        </p>
      </div>
      <textarea
        aria-label="Review comment"
        placeholder="Comment (optional, kept with a rejection)"
        value={comment}
        onChange={(e) => setComment(e.target.value)}
        rows={2}
      />
      {error && <p className="error">{error}</p>}
      <div className="row">
        <button disabled={busy} onClick={() => review(true)}>
          {isDemo ? 'Approve' : 'Approve and open PR'}
        </button>
        <button className="danger" disabled={busy} onClick={() => review(false)}>
          Reject
        </button>
      </div>
    </div>
  )
}

function Timeline({ steps, running, now, startedAt }: { steps: Step[]; running: boolean; now: number; startedAt: string }) {
  const last = steps.at(-1)
  const waitingSince = parseTime(last?.created_at ?? startedAt).getTime()
  return (
    <ol className="timeline">
      {steps.map((step, i) => (
        <li key={i} className={`step step-${step.status}`}>
          <details>
            <summary>
              <span className="dot" aria-hidden="true" />
              <span className="step-name">{STEP_LABELS[step.name] ?? step.name}</span>
              {step.status === 'error' && <span className="step-error">error</span>}
              <span className="step-time">{formatDuration(step.duration_ms)}</span>
            </summary>
            <div className="step-io">
              <p className="label">Input</p>
              <pre className="code small">{JSON.stringify(step.input, null, 2)}</pre>
              <p className="label">Output</p>
              <pre className="code small">{JSON.stringify(step.output, null, 2)}</pre>
            </div>
          </details>
        </li>
      ))}
      {running && (
        <li className="step step-active">
          <div className="summary-like">
            <span className="dot" aria-hidden="true" />
            <span className="step-name">Working on the next step…</span>
            <span className="step-time">{formatDuration(Math.max(0, now - waitingSince))}</span>
          </div>
        </li>
      )}
    </ol>
  )
}
