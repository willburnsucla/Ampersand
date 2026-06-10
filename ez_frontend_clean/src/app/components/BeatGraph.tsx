import { useEffect, useRef, useState } from "react";
import { Check, GripVertical, X } from "lucide-react";
import type { Beat } from "../../lib/types";

interface LocalBeat {
  id: string;
  logline: string;
  order: number;
  status: Beat["status"];
  turning_point: Beat["turning_point"];
  valence: number | null;
}

const TURNING_POINT_LABELS: Record<NonNullable<Beat["turning_point"]>, string> = {
  tp1: "Inciting Incident",
  tp2: "Rising Action",
  tp3: "Midpoint",
  tp4: "Dark Night",
  tp5: "Climax",
};

const STATUS_STYLES: Record<Beat["status"], string> = {
  committed: "bg-primary/10 text-primary border-primary/30",
  proposed:  "bg-accent/20 text-accent-foreground border-accent/50",
  rejected:  "bg-destructive/10 text-destructive border-destructive/30",
};

function valenceToSpineColor(valence: number | null): string {
  if (valence === null) return "border-primary bg-primary/10";
  if (valence > 0.3)  return "border-primary bg-primary/20";
  if (valence < -0.3) return "border-muted-foreground bg-muted";
  return "border-accent bg-accent/20";
}

function toLocal(beats: Beat[]): LocalBeat[] {
  return [...beats]
    .sort((a, b) => a.sequence_index_in_branch - b.sequence_index_in_branch)
    .map((b, i) => ({
      id: b.id,
      logline: b.logline,
      order: i,
      status: b.status,
      turning_point: b.turning_point,
      valence: b.valence,
    }));
}

export function BeatGraph({ beats, onDeleteBeat, onCommitBeat }: { beats: Beat[]; onDeleteBeat?: (id: string) => void; onCommitBeat?: (id: string) => void }) {
  const [local, setLocal] = useState<LocalBeat[]>(() => toLocal(beats));
  const [dragOverId, setDragOverId] = useState<string | null>(null);
  const dragIdRef = useRef<string | null>(null);

  useEffect(() => {
    setLocal(prev => {
      const incoming = toLocal(beats);
      const incomingIds = new Set(incoming.map(b => b.id));
      const prevIds = new Set(prev.map(b => b.id));
      // reconcile to the current branch: keep beats still present (preserving any local
      // drag order or edits), append new ones, and drop beats no longer here. switching
      // branches replaces every id, so this swaps the whole graph instead of piling the
      // old branch's beats onto the new one.
      const kept = prev.filter(b => incomingIds.has(b.id));
      const added = incoming.filter(b => !prevIds.has(b.id));
      if (added.length === 0 && kept.length === prev.length) return prev;
      return [...kept, ...added].map((b, i) => ({ ...b, order: i }));
    });
  }, [beats]);

  // Sync status/turning_point/valence for existing beats when server data refreshes
  useEffect(() => {
    const beatMap = new Map(beats.map(b => [b.id, b]));
    setLocal(prev =>
      prev.map(local => {
        const server = beatMap.get(local.id);
        if (!server) return local;
        return {
          ...local,
          status: server.status,
          turning_point: server.turning_point,
          valence: server.valence,
        };
      })
    );
  }, [beats]);

  const sorted = [...local].sort((a, b) => a.order - b.order);

  const saveEdit = (id: string, el: HTMLElement) => {
    const text = el.innerText.trim();
    if (text) setLocal(prev => prev.map(b => b.id === id ? { ...b, logline: text } : b));
    else el.innerText = local.find(b => b.id === id)?.logline ?? "";
  };

  const deleteBeat = (id: string) => {
    setLocal(prev => prev.filter(b => b.id !== id).map((b, i) => ({ ...b, order: i })));  // optimistic
    onDeleteBeat?.(id);  // persist; the parent refetches so a failure reverts
  };

  const commitBeat = (id: string) => {
    setLocal(prev => prev.map(b => b.id === id ? { ...b, status: "committed" } : b));  // optimistic
    onCommitBeat?.(id);  // persist; the parent refetches so a failure reverts
  };

  const onDragStart = (id: string) => { dragIdRef.current = id; };

  const onDragOver = (e: React.DragEvent, id: string) => {
    e.preventDefault();
    setDragOverId(id);
  };

  const onDrop = (targetId: string) => {
    const fromId = dragIdRef.current;
    if (!fromId || fromId === targetId) { setDragOverId(null); return; }
    setLocal(prev => {
      const s = [...prev].sort((a, b) => a.order - b.order);
      const fromIdx = s.findIndex(b => b.id === fromId);
      const toIdx   = s.findIndex(b => b.id === targetId);
      const reordered = [...s];
      const [moved] = reordered.splice(fromIdx, 1);
      reordered.splice(toIdx, 0, moved);
      return reordered.map((b, i) => ({ ...b, order: i }));
    });
    dragIdRef.current = null;
    setDragOverId(null);
  };

  if (sorted.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-10 text-center px-6">
        <p className="text-sm text-muted-foreground">
          No beats yet — send a message to add one.
        </p>
      </div>
    );
  }

  return (
    <div className="px-4 pb-4">
      {sorted.map((beat, i) => (
        <div
          key={beat.id}
          className="flex gap-3"
          onDragOver={e => onDragOver(e, beat.id)}
          onDrop={() => onDrop(beat.id)}
        >
          {/* Spine */}
          <div className="flex flex-col items-center flex-shrink-0 w-6">
            <div className={`w-6 h-6 rounded-full border-2 flex items-center justify-center flex-shrink-0 ${valenceToSpineColor(beat.valence)}`}>
              <span className="text-[9px] font-bold leading-none">{i + 1}</span>
            </div>
            {i < sorted.length - 1 && (
              <div className="w-px flex-1 bg-border my-1 min-h-[12px]" />
            )}
          </div>

          {/* Card */}
          <div className={`flex-1 group ${i < sorted.length - 1 ? "pb-3" : ""}`}>
            {/* Turning point label */}
            {beat.turning_point && (
              <p className="text-[9px] font-semibold uppercase tracking-wider text-primary/70 mb-0.5 pl-1">
                {TURNING_POINT_LABELS[beat.turning_point]}
              </p>
            )}

            <div
              className={`rounded-lg border bg-background/50 px-3 py-2 flex items-start gap-2 transition-colors ${
                dragOverId === beat.id ? "border-primary" : "border-border"
              } ${beat.status === "rejected" ? "opacity-50" : ""}`}
            >
              {/* Drag handle */}
              <div
                draggable
                onDragStart={() => onDragStart(beat.id)}
                className="mt-0.5 flex-shrink-0 cursor-grab active:cursor-grabbing text-muted-foreground/40 hover:text-muted-foreground transition-colors"
              >
                <GripVertical className="w-3 h-3" />
              </div>

              {/* Logline */}
              <p
                contentEditable={beat.status !== "rejected"}
                suppressContentEditableWarning
                className={`flex-1 text-xs leading-relaxed text-foreground cursor-text outline-none ${
                  beat.status === "rejected" ? "line-through cursor-not-allowed" : ""
                }`}
                onBlur={e => saveEdit(beat.id, e.currentTarget)}
                onKeyDown={e => {
                  if (e.key === "Enter")  { e.preventDefault(); e.currentTarget.blur(); }
                  if (e.key === "Escape") { e.currentTarget.innerText = beat.logline; e.currentTarget.blur(); }
                }}
              >
                {beat.logline}
              </p>

              {/* Commit a proposed beat (stays visible so the action is obvious) */}
              {beat.status === "proposed" && (
                <button
                  onClick={() => commitBeat(beat.id)}
                  title="Commit this beat"
                  className="flex-shrink-0 text-primary/70 hover:text-primary transition-colors mt-0.5"
                >
                  <Check className="w-3.5 h-3.5" />
                </button>
              )}

              {/* Delete */}
              <button
                onClick={() => deleteBeat(beat.id)}
                className="flex-shrink-0 opacity-0 group-hover:opacity-100 transition-opacity text-muted-foreground hover:text-destructive mt-0.5"
              >
                <X className="w-3 h-3" />
              </button>
            </div>

            {/* Status badge */}
            {beat.status !== "committed" && (
              <span className={`inline-block mt-1 ml-1 text-[9px] font-medium px-1.5 py-0.5 rounded border ${STATUS_STYLES[beat.status]}`}>
                {beat.status}
              </span>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
