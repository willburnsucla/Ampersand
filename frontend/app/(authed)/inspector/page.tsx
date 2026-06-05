'use client'

import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useApiClient } from '@/lib/use-api-client'
import { useStory } from '@/lib/story-context'
import type { Beat, Character, Theme, Setting } from '@/lib/types'

type Tab = 'characters' | 'beats' | 'themes' | 'settings'

const TABS: { type: Tab; label: string }[] = [
  { type: 'characters', label: 'Characters' },
  { type: 'beats',      label: 'Beats' },
  { type: 'themes',     label: 'Themes' },
  { type: 'settings',   label: 'Settings' },
]

export default function InspectorPage() {
  const [activeTab, setActiveTab] = useState<Tab>('characters')
  const { storyId, branchId } = useStory()

  return (
    <div className="flex flex-col h-full">
      <div className="flex border-b border-border px-6 gap-0 shrink-0">
        {TABS.map(({ type, label }) => (
          <button
            key={type}
            onClick={() => setActiveTab(type)}
            className={`px-4 py-3 text-sm font-medium border-b-2 transition-colors -mb-px ${
              activeTab === type
                ? 'border-foreground text-foreground'
                : 'border-transparent text-foreground/50 hover:text-foreground/80'
            }`}
          >
            {label}
          </button>
        ))}
      </div>
      <EntityList tab={activeTab} projectId={storyId} branchId={branchId} />
    </div>
  )
}

function EntityList({
  tab,
  projectId,
  branchId,
}: {
  tab: Tab
  projectId: string | null
  branchId: string | null
}) {
  const apiClient = useApiClient()

  const characters = useQuery({
    queryKey: ['characters', projectId],
    queryFn: () => apiClient.listCharacters(projectId!),
    enabled: tab === 'characters' && !!projectId,
  })

  const beats = useQuery({
    queryKey: ['beats', projectId, branchId],
    queryFn: () => apiClient.listBeats(projectId!, branchId!),
    enabled: tab === 'beats' && !!projectId && !!branchId,
  })

  const themes = useQuery({
    queryKey: ['themes', projectId],
    queryFn: () => apiClient.listThemes(projectId!),
    enabled: tab === 'themes' && !!projectId,
  })

  const settings = useQuery({
    queryKey: ['settings', projectId],
    queryFn: () => apiClient.listSettings(projectId!),
    enabled: tab === 'settings' && !!projectId,
  })

  const activeQuery = { characters, beats, themes, settings }[tab]
  const tabLabel = TABS.find((t) => t.type === tab)?.label.toLowerCase() ?? tab

  if (!projectId || !branchId) return <Empty label="Loading…" />
  if (activeQuery.isLoading) return <Empty label="Loading…" />
  if (activeQuery.isError) return <Empty label="Failed to load" />

  const items = activeQuery.data ?? []
  if (items.length === 0) {
    return <Empty label={`No ${tabLabel} yet — mention some in conversation.`} />
  }

  return (
    <div className="flex-1 overflow-y-auto px-6 py-4 space-y-3">
      {tab === 'beats' && (beats.data as Beat[]).map((b) => (
        <BeatCard key={b.id} beat={b} />
      ))}
      {tab === 'characters' && (characters.data as Character[]).map((c) => (
        <EntityCard key={c.id} name={c.name} status={c.status} properties={c.base_properties} />
      ))}
      {tab === 'themes' && (themes.data as Theme[]).map((t) => (
        <EntityCard key={t.id} name={t.name} status={t.status} properties={t.base_properties} />
      ))}
      {tab === 'settings' && (settings.data as Setting[]).map((s) => (
        <EntityCard key={s.id} name={s.name} status={s.status} properties={s.base_properties} />
      ))}
    </div>
  )
}

function Empty({ label }: { label: string }) {
  return (
    <div className="flex flex-1 items-center justify-center text-sm text-foreground/40">
      {label}
    </div>
  )
}

const STATUS_STYLES: Record<string, string> = {
  proposed:  'bg-yellow-100 text-yellow-800',
  committed: 'bg-green-100 text-green-800',
  rejected:  'bg-red-100 text-red-700 line-through',
}

function BeatCard({ beat }: { beat: Beat }) {
  return (
    <div className="rounded-lg border border-border p-4 space-y-2 bg-background hover:bg-foreground/[0.02] transition-colors">
      <div className="flex items-start justify-between gap-3">
        <span className="text-sm font-medium leading-snug">{beat.logline}</span>
        <span className={`shrink-0 text-xs px-2 py-0.5 rounded-full font-medium ${STATUS_STYLES[beat.status] ?? 'bg-gray-100 text-gray-600'}`}>
          {beat.status}
        </span>
      </div>
      <dl className="space-y-0.5">
        <div className="flex gap-2 text-xs">
          <dt className="text-foreground/40 shrink-0 min-w-[60px]">sequence:</dt>
          <dd className="text-foreground/70">#{beat.sequence_index_in_branch + 1}</dd>
        </div>
        {beat.turning_point && (
          <div className="flex gap-2 text-xs">
            <dt className="text-foreground/40 shrink-0 min-w-[60px]">turning pt:</dt>
            <dd className="text-foreground/70">{beat.turning_point}</dd>
          </div>
        )}
      </dl>
    </div>
  )
}

function EntityCard({
  name,
  status,
  properties,
}: {
  name: string
  status: string
  properties: Record<string, unknown>
}) {
  const entries = Object.entries(properties).filter(([, v]) => v !== undefined && v !== null && v !== '')
  return (
    <div className="rounded-lg border border-border p-4 space-y-2 bg-background hover:bg-foreground/[0.02] transition-colors">
      <div className="flex items-start justify-between gap-3">
        <span className="text-sm font-medium leading-snug">{name}</span>
        <span className={`shrink-0 text-xs px-2 py-0.5 rounded-full font-medium ${STATUS_STYLES[status] ?? 'bg-gray-100 text-gray-600'}`}>
          {status}
        </span>
      </div>
      {entries.length > 0 && (
        <dl className="space-y-0.5">
          {entries.map(([k, v]) => (
            <div key={k} className="flex gap-2 text-xs">
              <dt className="text-foreground/40 capitalize shrink-0 min-w-[60px]">{k.replace(/_/g, ' ')}:</dt>
              <dd className="text-foreground/70 truncate">{Array.isArray(v) ? v.join(', ') : String(v)}</dd>
            </div>
          ))}
        </dl>
      )}
    </div>
  )
}
