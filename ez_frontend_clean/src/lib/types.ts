// Types derived from backend/app/domain/models_v2.py
// Do not add fields that don't exist in the backend models

export interface Project {
  id: string;
  owner_id: string;
  title: string;
  primary_branch_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface Branch {
  id: string;
  project_id: string;
  parent_branch_id: string | null;
  state: "active" | "dormant" | "committed" | "graveyard";
  created_from_beat_id: string | null;
  name: string | null;
  created_at: string;
  updated_at: string;
}

export interface TurnRequest {
  project_id: string;
  branch_id: string;
  content: string;
}

export interface TurnResult {
  reply: string;
  beat: Beat | null;
}

export interface Beat {
  id: string;
  branch_id: string;
  sequence_index_in_branch: number;
  logline: string;
  turning_point: "tp1" | "tp2" | "tp3" | "tp4" | "tp5" | null;
  valence: number | null;
  arousal: number | null;
  status: "proposed" | "committed" | "rejected";
  created_at: string;
  updated_at: string;
}

export interface Character {
  id: string;
  project_id: string;
  name: string;
  base_properties: Record<string, unknown>;
  status: "proposed" | "committed" | "rejected";
  created_at: string;
  updated_at: string;
}

export interface Theme {
  id: string;
  project_id: string;
  name: string;
  base_properties: Record<string, unknown>;
  status: "proposed" | "committed" | "rejected";
  created_at: string;
  updated_at: string;
}

export interface Issue {
  id: string;
  branch_id: string;
  type: string;
  description: string;
  related_beat_ids: string[];
  related_entity_ids: string[];
  status: "open" | "resolved" | "dismissed";
  detected_at: string;
  resolved_at: string | null;
}

export interface ConversationTurn {
  id: string;
  branch_id: string;
  role: "writer" | "assistant";
  content: string;
  created_at: string;
}