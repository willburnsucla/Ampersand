'use client'

import { useStory } from '@/lib/story-context'
import { useGraphBootstrap } from '@/lib/use-graph-bootstrap'
import { ChatPane } from '@/components/conversation/chat-pane'
import { GraphStatsPane } from '@/components/conversation/graph-stats-pane'

export default function ConversationPage() {
  const { storyId, branchId, isLoading, error } = useStory()

  // Wire SSE + initial graph snapshot
  useGraphBootstrap(storyId, branchId)

  if (isLoading) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-foreground/50">
        Loading story…
      </div>
    )
  }

  if (error || !storyId || !branchId) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-red-500">
        {error ?? 'Failed to load story context.'}
      </div>
    )
  }

  return (
    <div className="flex h-full">
      {/* Chat — 60% */}
      <div className="flex-[3] border-r border-border overflow-hidden flex flex-col">
        <ChatPane storyId={storyId} branchId={branchId} />
      </div>
      {/* Graph stats — 40% */}
      <div className="flex-[2] overflow-auto">
        <GraphStatsPane />
      </div>
    </div>
  )
}
