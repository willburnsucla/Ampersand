/**
 * ApiClient — T-017 (stub).
 *
 * Sole HTTP entry point on the frontend. Full implementation in Week 2.
 * Types are imported from the shared schema types once `make codegen` runs.
 *
 * Architectural invariant #7: The frontend ONLY communicates with the backend
 * through ApiClient / SseClient / AuthClient. Never fetch() directly in components.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://localhost:8000'

class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

async function apiFetch<T>(
  path: string,
  options: RequestInit & { getToken?: () => Promise<string | null> } = {},
): Promise<T> {
  const { getToken, ...fetchOptions } = options

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(fetchOptions.headers as Record<string, string> ?? {}),
  }

  if (getToken) {
    const token = await getToken()
    if (token) headers['Authorization'] = `Bearer ${token}`
  }

  const res = await fetch(`${API_BASE}/api/v1${path}`, { ...fetchOptions, headers })

  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = await res.json()
      detail = body.detail ?? detail
    } catch {}
    throw new ApiError(res.status, String(res.status), detail)
  }

  return res.json() as Promise<T>
}

// ── ApiClient interface ────────────────────────────────────────────────────────

export interface ApiClient {
  // Stories
  listStories(): Promise<unknown[]>
  createStory(input: { title: string }): Promise<unknown>

  // Graph
  getGraph(storyId: string, branchId: string): Promise<unknown>

  // Branches
  createBranch(input: {
    story_id: string
    parent_branch_id?: string
    created_from_beat_id?: string
    name?: string
  }): Promise<unknown>
  transitionBranch(branchId: string, event: string): Promise<unknown>
  listBranches(storyId: string): Promise<unknown[]>

  // Conversation
  postTurn(req: { story_id: string; branch_id: string; content: string }): Promise<unknown>

  // Export
  exportStory(storyId: string, opts?: { branch_id?: string; include_alternative_branches?: boolean }): Promise<unknown>

  // Queries
  query(input: { story_id: string; branch_id: string; question: string }): Promise<unknown>

  // Gaps
  getGaps(storyId: string, branchId: string): Promise<unknown[]>

  // Visualizations
  getViz(storyId: string, branchId: string, kind: 'character_arcs' | 'tension_curve' | 'structure_heatmap'): Promise<unknown>
}

// ── HttpApiClient implementation ──────────────────────────────────────────────

export class HttpApiClient implements ApiClient {
  private getToken: () => Promise<string | null>

  constructor(getToken: () => Promise<string | null>) {
    this.getToken = getToken
  }

  private fetch<T>(path: string, options: RequestInit = {}): Promise<T> {
    return apiFetch<T>(path, { ...options, getToken: this.getToken })
  }

  async listStories() {
    return this.fetch<unknown[]>('/stories')
  }

  async createStory(input: { title: string }) {
    return this.fetch('/stories', {
      method: 'POST',
      body: JSON.stringify(input),
    })
  }

  async getGraph(storyId: string, branchId: string) {
    return this.fetch(`/stories/${storyId}/graph?branch_id=${branchId}`)
  }

  async createBranch(input: object) {
    return this.fetch('/branches', {
      method: 'POST',
      body: JSON.stringify(input),
    })
  }

  async transitionBranch(branchId: string, event: string) {
    return this.fetch(`/branches/${branchId}/transition`, {
      method: 'POST',
      body: JSON.stringify({ event }),
    })
  }

  async listBranches(storyId: string) {
    return this.fetch<unknown[]>(`/stories/${storyId}/branches`)
  }

  async postTurn(req: object) {
    return this.fetch('/conversation/turn', {
      method: 'POST',
      body: JSON.stringify(req),
    })
  }

  async exportStory(storyId: string, opts?: object) {
    const params = new URLSearchParams(opts as Record<string, string>)
    return this.fetch(`/stories/${storyId}/export?${params}`)
  }

  async query(input: object) {
    return this.fetch('/queries', {
      method: 'POST',
      body: JSON.stringify(input),
    })
  }

  async getGaps(storyId: string, branchId: string) {
    return this.fetch<unknown[]>(`/stories/${storyId}/gaps?branch_id=${branchId}`)
  }

  async getViz(storyId: string, branchId: string, kind: string) {
    return this.fetch(`/stories/${storyId}/visualizations/${kind}?branch_id=${branchId}`)
  }
}
