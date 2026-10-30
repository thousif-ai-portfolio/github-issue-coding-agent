// Types and calls for the agent's REST API (agent/main.py). In development Vite proxies
// /api to uvicorn on port 8000; in production FastAPI serves this app itself.

export type RunStatus =
  | 'running'
  | 'awaiting_approval'
  | 'approved'
  | 'pr_opened'
  | 'rejected'
  | 'failed'
  | 'skipped'
  | 'suggested' // week 1 runs, before the approval step existed

export type Source = 'demo' | 'github'

export interface Issue {
  number: number
  title: string
  body: string
  url: string
}

export interface Step {
  name: string
  status: string
  input: Record<string, unknown>
  output: Record<string, unknown>
  duration_ms: number
  created_at: string
}

export interface RunSummary {
  id: number
  repo: string
  issue_number: number
  issue_title: string
  status: RunStatus
  created_at: string
  finished_at: string | null
}

export interface RunDetail extends RunSummary {
  model: string
  explanation: string
  diff: string
  error: string
  test_output: string
  regression_test: string
  pr_url: string
  steps: Step[]
}

export interface Health {
  status: string
  model: string
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...init?.headers },
  })
  if (!response.ok) {
    let message = `${response.status} ${response.statusText}`
    try {
      const body = await response.json()
      if (typeof body.detail === 'string') message = body.detail
      else if (Array.isArray(body.detail)) message = body.detail.map((d: { msg: string }) => d.msg).join('; ')
    } catch {
      // The body was not JSON; keep the status line.
    }
    throw new Error(message)
  }
  return response.json() as Promise<T>
}

export const api = {
  health: () => request<Health>('/api/health'),
  issues: (source: Source, repo?: string) => {
    const params = new URLSearchParams({ source })
    if (repo) params.set('repo', repo)
    return request<Issue[]>(`/api/issues?${params}`)
  },
  runs: () => request<RunSummary[]>('/api/runs'),
  run: (id: number) => request<RunDetail>(`/api/runs/${id}`),
  startRun: (source: Source, issueNumber: number, repo?: string) =>
    request<RunSummary>('/api/runs', {
      method: 'POST',
      body: JSON.stringify({ source, issue_number: issueNumber, repo: repo || null }),
    }),
  review: (id: number, approved: boolean, comment: string) =>
    request<RunSummary>(`/api/runs/${id}/${approved ? 'approve' : 'reject'}`, {
      method: 'POST',
      body: JSON.stringify({ comment }),
    }),
}

export const STATUS_LABELS: Record<RunStatus, string> = {
  running: 'Running',
  awaiting_approval: 'Needs review',
  approved: 'Approved',
  pr_opened: 'PR opened',
  rejected: 'Rejected',
  failed: 'Failed',
  skipped: 'Skipped',
  suggested: 'Suggested',
}

export const STEP_LABELS: Record<string, string> = {
  fetch_issue: 'Fetch issue',
  prepare_workspace: 'Copy repository',
  classify: 'Classify issue',
  search_code: 'Search code',
  choose_files: 'Pick files',
  write_test: 'Write regression test',
  propose_patch: 'Propose fix',
  run_tests: 'Run tests in sandbox',
  human_review: 'Human review',
  open_pr: 'Open draft PR',
  save_patch: 'Save patch',
}

// SQLite timestamps are UTC ISO strings, e.g. "2026-10-30T09:12:44+00:00".
export function parseTime(value: string): Date {
  return new Date(/[zZ]|[+-]\d\d:\d\d$/.test(value) ? value : `${value}Z`)
}

export function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms} ms`
  const seconds = ms / 1000
  if (seconds < 60) return `${seconds.toFixed(1)} s`
  const minutes = Math.floor(seconds / 60)
  return `${minutes} min ${Math.round(seconds % 60)} s`
}

export function timeAgo(value: string, now: number = Date.now()): string {
  const seconds = Math.max(0, Math.round((now - parseTime(value).getTime()) / 1000))
  if (seconds < 60) return `${seconds}s ago`
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  return parseTime(value).toLocaleDateString()
}
