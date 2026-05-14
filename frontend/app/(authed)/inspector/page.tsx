'use client'

import { useState } from 'react'
import { useGraphReady, useNodesByType, type NodeType } from '@/lib/graph-store'
import { NodeCard } from '@/components/inspector/node-card'

const TABS: { type: NodeType; label: string }[] = [
  { type: 'character',     label: 'Characters' },
  { type: 'beat',          label: 'Beats' },
  { type: 'theme',         label: 'Themes' },
  { type: 'world_element', label: 'World Elements' },
  { type: 'thread',        label: 'Threads' },
]

export default function InspectorPage() {
  const [activeType, setActiveType] = useState<NodeType>('character')
  const isReady = useGraphReady()

  if (!isReady) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-foreground/50">
        Loading graph…
      </div>
    )
  }

  return (
    <div className="flex flex-col h-full">
      {/* Tab bar */}
      <div className="flex border-b border-border px-6 gap-0 shrink-0">
        {TABS.map(({ type, label }) => (
          <button
            key={type}
            onClick={() => setActiveType(type)}
            className={`px-4 py-3 text-sm font-medium border-b-2 transition-colors -mb-px ${
              activeType === type
                ? 'border-foreground text-foreground'
                : 'border-transparent text-foreground/50 hover:text-foreground/80'
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Node list — separate component so useNodesByType only re-renders this subtree */}
      <NodeList type={activeType} />
    </div>
  )
}

function NodeList({ type }: { type: NodeType }) {
  const nodes = useNodesByType(type)
  const label = TABS.find((t) => t.type === type)?.label ?? type

  if (nodes.length === 0) {
    return (
      <div className="flex flex-1 items-center justify-center text-sm text-foreground/40">
        No {label.toLowerCase()} yet — mention some in conversation.
      </div>
    )
  }

  return (
    <div className="flex-1 overflow-y-auto px-6 py-4 space-y-3">
      {nodes.map((node) => (
        <NodeCard key={node.id} node={node} />
      ))}
    </div>
  )
}
