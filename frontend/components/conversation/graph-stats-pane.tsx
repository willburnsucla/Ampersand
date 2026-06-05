'use client'

import { useQuery } from '@tanstack/react-query'
import { useApiClient } from '@/lib/use-api-client'
import { useStory } from '@/lib/story-context'

export function GraphStatsPane() {
  const { storyId, branchId } = useStory()
  const apiClient = useApiClient()

  const beats      = useQuery({ queryKey: ['beats', storyId, branchId],  queryFn: () => apiClient.listBeats(storyId!, branchId!),   enabled: !!storyId && !!branchId })
  const characters = useQuery({ queryKey: ['characters', storyId],        queryFn: () => apiClient.listCharacters(storyId!),         enabled: !!storyId })
  const themes     = useQuery({ queryKey: ['themes', storyId],            queryFn: () => apiClient.listThemes(storyId!),             enabled: !!storyId })
  const settings   = useQuery({ queryKey: ['settings', storyId],          queryFn: () => apiClient.listSettings(storyId!),           enabled: !!storyId })
  const issues     = useQuery({ queryKey: ['issues', storyId, branchId],  queryFn: () => apiClient.listIssues(storyId!, branchId!),  enabled: !!storyId && !!branchId })

  const isLoading = beats.isLoading || characters.isLoading
  const isReady = !isLoading && !!storyId

  const ROWS = [
    { label: 'Beats',      count: beats.data?.length },
    { label: 'Characters', count: characters.data?.length },
    { label: 'Themes',     count: themes.data?.length },
    { label: 'Settings',   count: settings.data?.length },
  ]

  const openIssues = issues.data?.filter((i) => i.status === 'open') ?? []

  return (
    <div className="px-6 py-6 space-y-6">
      {/* Connection status — matches original dot indicator */}
      <div className="flex items-center gap-2">
        <span
          className={`inline-block w-2 h-2 rounded-full shrink-0 ${
            isReady ? 'bg-green-500' : 'bg-yellow-400 animate-pulse'
          }`}
        />
        <span className="text-xs text-foreground/60">
          {isReady ? 'Story synced' : 'Loading…'}
        </span>
      </div>

      {/* Entity counts */}
      <div className="space-y-3">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-foreground/40">
          Story Graph
        </h3>
        {isReady ? (
          <div className="space-y-2">
            {ROWS.map(({ label, count }) => (
              <div key={label} className="flex items-center justify-between text-sm">
                <span className="text-foreground/70">{label}</span>
                <span className="font-mono font-medium tabular-nums">{count ?? 0}</span>
              </div>
            ))}
          </div>
        ) : (
          <div className="space-y-2">
            {Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="flex justify-between">
                <div className="h-3 w-24 rounded bg-foreground/10 animate-pulse" />
                <div className="h-3 w-5 rounded bg-foreground/10 animate-pulse" />
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Open issues */}
      {openIssues.length > 0 && (
        <div className="space-y-2">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-foreground/40">
            Issues
          </h3>
          {openIssues.map((issue) => (
            <div key={issue.id} className="text-xs border border-border rounded px-3 py-2">
              <span className="font-medium text-yellow-600">{issue.type.replace(/_/g, ' ')}</span>
              <p className="mt-0.5 text-foreground/50 leading-snug">{issue.description}</p>
            </div>
          ))}
        </div>
      )}

      {isReady && (
        <p className="text-xs text-foreground/30 leading-relaxed">
          Graph updates live as you write. Open Inspector to browse nodes.
        </p>
      )}
    </div>
  )
}
