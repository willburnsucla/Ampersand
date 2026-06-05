import type { Beat } from "../../lib/types";

const NODE_W = 130;
const NODE_H = 60;
const GAP = 36;
const PAD = 12;

export function BeatGraph({ beats }: { beats: Beat[] }) {
  const sorted = [...beats].sort(
    (a, b) => a.sequence_index_in_branch - b.sequence_index_in_branch
  );

  if (sorted.length === 0) {
    return (
      <p className="text-sm text-muted-foreground text-center py-6">
        No beats yet — send a message to add one.
      </p>
    );
  }

  const svgW = PAD + sorted.length * NODE_W + (sorted.length - 1) * GAP + PAD;
  const svgH = NODE_H + PAD * 2;
  const cy = PAD + NODE_H / 2;

  return (
    <div className="overflow-x-auto">
      <svg width={svgW} height={svgH}>
        <defs>
          <marker
            id="beat-arrow"
            markerWidth="7"
            markerHeight="7"
            refX="6"
            refY="3.5"
            orient="auto"
          >
            <path d="M0,0 L0,7 L7,3.5 z" fill="var(--border)" />
          </marker>
        </defs>

        {sorted.map((beat, i) => {
          const x = PAD + i * (NODE_W + GAP);
          return (
            <g key={beat.id}>
              {i > 0 && (
                <line
                  x1={x - GAP + 2}
                  y1={cy}
                  x2={x - 2}
                  y2={cy}
                  stroke="var(--border)"
                  strokeWidth={2}
                  markerEnd="url(#beat-arrow)"
                />
              )}

              <rect
                x={x}
                y={PAD}
                width={NODE_W}
                height={NODE_H}
                rx={8}
                fill="var(--card)"
                stroke="var(--primary)"
                strokeWidth={1.5}
              />

              <text
                x={x + 8}
                y={PAD + 13}
                fontSize={9}
                fill="var(--primary)"
                fontFamily="inherit"
                fontWeight="600"
              >
                Beat {beat.sequence_index_in_branch + 1}
              </text>

              <foreignObject
                x={x + 4}
                y={PAD + 18}
                width={NODE_W - 8}
                height={NODE_H - 22}
              >
                <div
                  style={{
                    fontSize: "10px",
                    lineHeight: "1.35",
                    overflow: "hidden",
                    display: "-webkit-box",
                    WebkitLineClamp: 3,
                    WebkitBoxOrient: "vertical",
                    color: "var(--foreground)",
                    fontFamily: "inherit",
                  }}
                >
                  {beat.logline}
                </div>
              </foreignObject>
            </g>
          );
        })}
      </svg>
    </div>
  );
}
