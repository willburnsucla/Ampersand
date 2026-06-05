import type {
  Beat,
  Branch,
  Character,
  Issue,
  Project,
  Theme,
  TurnRequest,
  TurnResult,
} from "./types";
import { supabase } from "./supabase";

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";
const API_V2_BASE = `${BASE_URL}/api/v2`;

async function getToken(): Promise<string> {
  const { data: { session } } = await supabase.auth.getSession()
  return session?.access_token ?? "mock"
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = await getToken()
  const res = await fetch(`${API_V2_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
      ...options.headers,
    },
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API ${res.status} on ${path}: ${text}`);
  }

  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export async function listProjects(): Promise<Project[]> {
  return request<Project[]>("/projects");
}

export async function createProject(input: { title: string }): Promise<Project> {
  return request<Project>("/projects", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export async function createBranch(input: {
  project_id: string;
  name?: string | null;
}): Promise<Branch> {
  return request<Branch>("/branches", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export async function forkBranch(input: {
  project_id: string;
  parent_branch_id: string;
  from_beat_id: string;
  name?: string | null;
}): Promise<Branch> {
  return request<Branch>("/branches/fork", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export async function listBeats(projectId: string, branchId: string): Promise<Beat[]> {
  return request<Beat[]>(`/projects/${projectId}/branches/${branchId}/beats`);
}

export async function deleteBeat(projectId: string, branchId: string, beatId: string): Promise<void> {
  await request<void>(`/projects/${projectId}/branches/${branchId}/beats/${beatId}`, {
    method: "DELETE",
  });
}

export async function listBranches(projectId: string): Promise<Branch[]> {
  return request<Branch[]>(`/projects/${projectId}/branches`);
}

export async function listCharacters(projectId: string): Promise<Character[]> {
  return request<Character[]>(`/projects/${projectId}/characters`);
}

export async function listThemes(projectId: string): Promise<Theme[]> {
  return request<Theme[]>(`/projects/${projectId}/themes`);
}

export async function listIssues(projectId: string, branchId: string): Promise<Issue[]> {
  return request<Issue[]>(`/projects/${projectId}/branches/${branchId}/issues`);
}

export async function deleteProject(projectId: string): Promise<void> {
  await request<void>(`/projects/${projectId}`, { method: "DELETE" });
}

export async function sendTurn(body: TurnRequest): Promise<TurnResult> {
  return request<TurnResult>("/conversation/turn", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

// Session is stored in sessionStorage so a page refresh reuses the same project/branch.
const SESSION_KEY = "ampersand_session_v2";

interface Session {
  projectId: string;
  branchId: string;
}

export async function getOrCreateSession(title = "My Story"): Promise<Session> {
  const projects = await listProjects();

  const cached = sessionStorage.getItem(SESSION_KEY);
  if (cached) {
    try {
      const session = JSON.parse(cached) as Session;
      if (projects.some((p) => p.id === session.projectId)) {
        return session;
      }
    } catch (err) {
      console.warn("Failed to validate cached session, regenerating...", err);
    }
    clearSession();
  }

  // Reuse the first existing project/branch instead of creating a duplicate
  if (projects.length > 0) {
    const project = projects[0];
    const branches = await listBranches(project.id);
    if (branches.length > 0) {
      const session: Session = { projectId: project.id, branchId: branches[0].id };
      sessionStorage.setItem(SESSION_KEY, JSON.stringify(session));
      return session;
    }
  }

  const project = await createProject({ title });
  const branch = await createBranch({ project_id: project.id, name: "main" });

  const session: Session = { projectId: project.id, branchId: branch.id };
  sessionStorage.setItem(SESSION_KEY, JSON.stringify(session));
  return session;
}

export function clearSession(): void {
  sessionStorage.removeItem(SESSION_KEY);
}
