import { useEffect, useRef, useState } from "react";
import { GripVertical, X } from "lucide-react";
import type { Beat } from "../../lib/types";

interface LocalBeat {
  id: string;
  logline: string;
  order: number;
}

function toLocal(beats: Beat[]): LocalBeat[] {
  return [...beats]
    .sort((a, b) => a.sequence_index_in_branch - b.sequence_index_in_branch)
    .map((b, i) => ({ id: b.id, logline: b.logline, order: i }));
}

export function BeatGraph({ beats }: { beats: Beat[] }) {
  const [local, setLocal] = useState<LocalBeat[]>(() => toLocal(beats));
  const [dragOverId, setDragOverId] = useState<string | null>(null);
  const dragIdRef = useRef<string | null>(null);

  // Merge new beats from server without overwriting user edits
  useEffect(() => {
    setLocal(prev => {
      const existingIds = new Set(prev.map(b => b.id));
      const incoming = toLocal(beats);
      const newOnes = incoming.filter(b => !existingIds.has(b.id));
      if (newOnes.length === 0) return prev;
      return [...prev, ...newOnes].map((b, i) => ({ ...b, order: i }));
    });
  }, [beats]);

  const sorted = [...local].sort((a, b) => a.order - b.order);

  const saveEdit = (id: string, el: HTMLElement) => {
    const text = el.innerText.trim();
    if (text) setLocal(prev => prev.map(b => b.id === id ? { ...b, logline: text } : b));
    else el.innerText = local.find(b => b.id === id)?.logline ?? "";
  };

  const deleteBeat = (id: string) => {
    setLocal(prev => prev.filter(b => b.id !== id).map((b, i) => ({ ...b, order: i })));
  };

  const onDragStart = (id: string) => {
    dragIdRef.current = id;
  };

  const onDragOver = (e: React.DragEvent, id: string) => {
    e.preventDefault();
    setDragOverId(id);
  };

  const onDrop = (targetId: string) => {
    const fromId = dragIdRef.current;
    if (!fromId || fromId === targetId) {
      setDragOverId(null);
      return;
    }
    setLocal(prev => {
      const sorted = [...prev].sort((a, b) => a.order - b.order);
      const fromIdx = sorted.findIndex(b => b.id === fromId);
      const toIdx = sorted.findIndex(b => b.id === targetId);
      const reordered = [...sorted];
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
            <div className="w-6 h-6 rounded-full bg-primary/10 border-2 border-primary flex items-center justify-center flex-shrink-0">
              <span className="text-[9px] font-bold text-primary leading-none">{i + 1}</span>
            </div>
            {i < sorted.length - 1 && (
              <div className="w-px flex-1 bg-border my-1 min-h-[12px]" />
            )}
          </div>

          {/* Card */}
          <div className={`flex-1 group ${i < sorted.length - 1 ? "pb-3" : ""}`}>
            <div
              className={`rounded-lg border bg-background/50 px-3 py-2 flex items-start gap-2 transition-colors ${
                dragOverId === beat.id ? "border-primary" : "border-border"
              }`}
            >
              {/* Drag handle */}
              <div
                draggable
                onDragStart={() => onDragStart(beat.id)}
                className="mt-0.5 flex-shrink-0 cursor-grab active:cursor-grabbing text-muted-foreground/40 hover:text-muted-foreground transition-colors"
              >
                <GripVertical className="w-3 h-3" />
              </div>

              {/* Logline: contentEditable so node size never changes */}
              <p
                contentEditable
                suppressContentEditableWarning
                className="flex-1 text-xs leading-relaxed text-foreground cursor-text outline-none"
                onBlur={e => saveEdit(beat.id, e.currentTarget)}
                onKeyDown={e => {
                  if (e.key === "Enter") { e.preventDefault(); e.currentTarget.blur(); }
                  if (e.key === "Escape") { e.currentTarget.innerText = beat.logline; e.currentTarget.blur(); }
                }}
              >
                {beat.logline}
              </p>

              {/* Delete */}
              <button
                onClick={() => deleteBeat(beat.id)}
                className="flex-shrink-0 opacity-0 group-hover:opacity-100 transition-opacity text-muted-foreground hover:text-destructive mt-0.5"
              >
                <X className="w-3 h-3" />
              </button>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}
