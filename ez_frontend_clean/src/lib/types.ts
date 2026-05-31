// Types derived from backend/app/domain/models.py
// Do not add fields that don't exist in the backend models

export interface Story {
  id: string;
  owner_id: string;
  title: string;
  active_branch_id: string | null;
  created_at: string;
}

export interface CreateStoryInput {
  title: string;
}

export interface Branch {
  id: string;
  story_id: string;
  parent_branch_id: string | null;
  state: "active" | "dormant" | "committed" | "graveyard";
  created_from_beat_id: string | null;
  name: string | null;
  created_at: string;
}

export interface CreateBranchInput {
  story_id: string;
  parent_branch_id?: string | null;
  created_from_beat_id?: string | null;
  name?: string | null;
}

export interface TurnRequest {
  story_id: string;
  branch_id: string;
  content: string;
}

export interface TurnResult {
  turn_id: string;
  reply: string;
  applied_delta: {
    delta: { turn_id: string; ops: unknown[] };
    affected_node_ids: string[];
    affected_edge_ids: string[];
  };
}