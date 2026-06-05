// Mirrors backend/app/domain/models_v2.py — keep in sync, no extra fields

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