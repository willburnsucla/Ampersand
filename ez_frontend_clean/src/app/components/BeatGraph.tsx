import type { Beat } from "../../lib/types";

export function BeatGraph({ beats }: { beats: Beat[] }) {
  const sorted = [...beats].sort(
    (a, b) => a.sequence_index_in_branch - b.sequence_index_in_branch
  );

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
        <div key={beat.id} className="flex gap-3">
          {/* Spine: circle + connector line */}
          <div className="flex flex-col items-center flex-shrink-0 w-6">
            <div className="w-6 h-6 rounded-full bg-primary/10 border-2 border-primary flex items-center justify-center flex-shrink-0">
              <span className="text-[9px] font-bold text-primary leading-none">
                {beat.sequence_index_in_branch + 1}
              </span>
            </div>
            {i < sorted.length - 1 && (
              <div className="w-px flex-1 bg-border my-1 min-h-[12px]" />
            )}
          </div>

          {/* Beat card */}
          <div className={`flex-1 ${i < sorted.length - 1 ? "pb-3" : ""}`}>
            <div className="rounded-lg border border-border bg-background/50 px-3 py-2">
              <p className="text-xs leading-relaxed text-foreground">
                {beat.logline}
              </p>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}
