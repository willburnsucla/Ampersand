import type {
  Branch,
  CreateBranchInput,
  CreateStoryInput,
  Story,
  TurnRequest,
  TurnResult,
} from "./types";

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";
const API_BASE = `${BASE_URL}/api/v1`;

// In mock mode the backend accepts any token. When Clerk is wired in,
// replace this with a real JWT from your auth client.
const AUTH_TOKEN = "mock";

async function request<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${AUTH_TOKEN}`,
      ...options.headers,
    },
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API ${res.status} on ${path}: ${text}`);
  }

  return res.json() as Promise<T>;
}

// ── Stories ────────────────────────────────────────────────────────────────

export async function listStories(): Promise<Story[]> {
  return request<Story[]>("/stories");
}

export async function createStory(input: CreateStoryInput): Promise<Story> {
  return request<Story>("/stories", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

// ── Branches ───────────────────────────────────────────────────────────────

export async function listBranches(storyId: string): Promise<Branch[]> {
  return request<Branch[]>(`/stories/${storyId}/branches`);
}

export async function createBranch(input: CreateBranchInput): Promise<Branch> {
  return request<Branch>("/branches", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

// ── Conversation ───────────────────────────────────────────────────────────

export async function sendTurn(body: TurnRequest): Promise<TurnResult> {
  return request<TurnResult>("/conversation/turn", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

// ── Session bootstrap ──────────────────────────────────────────────────────
// Creates (or reuses) a story + branch for the current chat session.
// Stored in sessionStorage so a page refresh reuses the same IDs.

const SESSION_KEY = "ampersand_session";

interface Session {
  storyId: string;
  branchId: string;
}

export async function getOrCreateSession(title = "My Story"): Promise<Session> {
  const cached = sessionStorage.getItem(SESSION_KEY);
  if (cached) {
    return JSON.parse(cached) as Session;
  }

  const story = await createStory({ title });
  const branch = await createBranch({ story_id: story.id, name: "main" });

  const session: Session = { storyId: story.id, branchId: branch.id };
  sessionStorage.setItem(SESSION_KEY, JSON.stringify(session));
  return session;
}

export function clearSession(): void {
  sessionStorage.removeItem(SESSION_KEY);
}