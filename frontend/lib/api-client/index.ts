/**
 * ApiClient — sole HTTP entry point on the frontend.
 *
 * Architectural invariant #7: The frontend ONLY communicates with the backend
 * through ApiClient / SseClient / AuthClient. Never fetch() directly in components.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://localhost:8000'

export class ApiError extends Error {
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

  const res = await fetch(`${API_BASE}${path}`, { ...fetchOptions, headers })

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

// HttpApiClient

import type {
  Project, Branch, Beat, Character, Theme, Setting,
  Issue, ConversationTurn, TurnResultV2,
  Story, GraphSnapshot, TurnResult,
} from '@/lib/types'

export class HttpApiClient {
  private getToken: () => Promise<string | null>

  constructor(getToken: () => Promise<string | null>) {
    this.getToken = getToken
  }

  private v1<T>(path: string, options: RequestInit = {}): Promise<T> {
    return apiFetch<T>(`/api/v1${path}`, { ...options, getToken: this.getToken })
  }

  private v2<T>(path: string, options: RequestInit = {}): Promise<T> {
    return apiFetch<T>(`/api/v2${path}`, { ...options, getToken: this.getToken })
  }

  // v2: projects

  listProjects(): Promise<Project[]> {
    return this.v2('/projects')
  }

  createProject(input: { title: string }): Promise<Project> {
    return this.v2('/projects', { method: 'POST', body: JSON.stringify(input) })
  }

  // v2: branches

  listBranchesV2(projectId: string): Promise<Branch[]> {
    return this.v2(`/projects/${projectId}/branches`)
  }

  createBranchV2(input: {
    project_id: string
    name?: string
    parent_branch_id?: string
    created_from_beat_id?: string
  }): Promise<Branch> {
    return this.v2('/branches', { method: 'POST', body: JSON.stringify(input) })
  }

  // v2: entities

  listBeats(projectId: string, branchId: string): Promise<Beat[]> {
    return this.v2(`/projects/${projectId}/branches/${branchId}/beats`)
  }

  listCharacters(projectId: string): Promise<Character[]> {
    return this.v2(`/projects/${projectId}/characters`)
  }

  listThemes(projectId: string): Promise<Theme[]> {
    return this.v2(`/projects/${projectId}/themes`)
  }

  listSettings(projectId: string): Promise<Setting[]> {
    return this.v2(`/projects/${projectId}/settings`)
  }

  listIssues(projectId: string, branchId: string): Promise<Issue[]> {
    return this.v2(`/projects/${projectId}/branches/${branchId}/issues`)
  }

  listTurns(projectId: string, branchId: string): Promise<ConversationTurn[]> {
    return this.v2(`/projects/${projectId}/branches/${branchId}/turns`)
  }

  // v2: conversation turn

  postTurnV2(req: { project_id: string; branch_id: string; content: string }): Promise<TurnResultV2> {
    return this.v2('/conversation/turn', { method: 'POST', body: JSON.stringify(req) })
  }

  // v1: legacy (graph-store / SSE bootstrap)

  listStories(): Promise<Story[]> {
    return this.v1('/stories')
  }

  createStory(input: { title: string }): Promise<Story> {
    return this.v1('/stories', { method: 'POST', body: JSON.stringify(input) })
  }

  getGraph(storyId: string, branchId: string): Promise<GraphSnapshot> {
    return this.v1(`/stories/${storyId}/graph?branch_id=${branchId}`)
  }

  postTurn(req: { story_id: string; branch_id: string; content: string }): Promise<TurnResult> {
    return this.v1('/conversation/turn', { method: 'POST', body: JSON.stringify(req) })
  }
}