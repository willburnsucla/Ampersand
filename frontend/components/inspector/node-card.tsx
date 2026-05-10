import type { StoryNode } from '@/lib/graph-store'

const STATUS_STYLES: Record<string, string> = {
  proposed:  'bg-yellow-100 text-yellow-800',
  committed: 'bg-green-100 text-green-800',
  rejected:  'bg-red-100 text-red-700 line-through',
}

// Key properties to surface per node type
const KEY_PROPS: Record<string, string[]> = {
  character:     ['role', 'motivation'],
  beat:          ['sequence_index', 'description'],
  theme:         ['description'],
  world_element: ['rules'],
  thread:        ['setup_beat_id'],
}

export function NodeCard({ node }: { node: StoryNode }) {
  const name =
    (node.properties.name as string | undefined) ||
    (node.properties.title as string | undefined) ||
    node.id.slice(0, 8)

  const keyProps = KEY_PROPS[node.type] ?? []

  return (
    <div className="rounded-lg border border-border p-4 space-y-2 bg-background hover:bg-foreground/[0.02] transition-colors">
      <div className="flex items-start justify-between gap-3">
        <span className="text-sm font-medium leading-snug">{name}</span>
        <span
          className={`shrink-0 text-xs px-2 py-0.5 rounded-full font-medium ${
            STATUS_STYLES[node.status] ?? 'bg-gray-100 text-gray-600'
          }`}
        >
          {node.status}
        </span>
      </div>
      {keyProps.length > 0 && (
        <dl className="space-y-0.5">
          {keyProps.map((key) => {
            const val = node.properties[key]
            if (val === undefined || val === null || val === '') return null
            const display = Array.isArray(val) ? val.join(', ') : String(val)
            return (
              <div key={key} className="flex gap-2 text-xs">
                <dt className="text-foreground/40 capitalize shrink-0 min-w-[60px]">
                  {key.replace(/_/g, ' ')}:
                </dt>
                <dd className="text-foreground/70 truncate">{display}</dd>
              </div>
            )
          })}
        </dl>
      )}
    </div>
  )
}
