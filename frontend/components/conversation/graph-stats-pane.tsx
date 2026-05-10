'use client'

import { useGraphStore, useGraphReady, type NodeType } from '@/lib/graph-store'

const NODE_TYPE_LABELS: Record<NodeType, string> = {
  character:     'Characters',
  beat:          'Beats',
  theme:         'Themes',
  world_element: 'World Elements',
  thread:        'Threads',
}

export function GraphStatsPane() {
  const isReady = useGraphReady()
  const byType = useGraphStore((s) => s.byType)
  const resyncInFlight = useGraphStore((s) => s.resyncInFlight)

  return (
    <div className="px-6 py-6 space-y-6">
      {/* Connection status */}
      <div className="flex items-center gap-2">
        <span
          className={`inline-block w-2 h-2 rounded-full shrink-0 ${
            isReady ? 'bg-green-500' : 'bg-yellow-400 animate-pulse'
          }`}
        />
        <span className="text-xs text-foreground/60">
          {resyncInFlight
            ? 'Resyncing graph…'
            : isReady
            ? 'Graph synced'
            : 'Connecting…'}
        </span>
      </div>

      {/* Node type counts */}
      <div className="space-y-3">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-foreground/40">
          Story Graph
        </h3>
        {isReady ? (
          <div className="space-y-2">
            {(Object.entries(NODE_TYPE_LABELS) as [NodeType, string][]).map(([type, label]) => (
              <div key={type} className="flex items-center justify-between text-sm">
                <span className="text-foreground/70">{label}</span>
                <span className="font-mono font-medium tabular-nums">
                  {byType[type]?.length ?? 0}
                </span>
              </div>
            ))}
          </div>
        ) : (
          <div className="space-y-2">
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="flex justify-between">
                <div className="h-3 w-24 rounded bg-foreground/10 animate-pulse" />
                <div className="h-3 w-5 rounded bg-foreground/10 animate-pulse" />
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Hint */}
      {isReady && (
        <p className="text-xs text-foreground/30 leading-relaxed">
          Graph updates live as you write. Open Inspector to browse nodes.
        </p>
      )}
    </div>
  )
}
