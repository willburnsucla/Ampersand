'use client'

/**
 * StoryContext — bootstraps the active story + branch on mount.
 *
 * Bootstrap sequence:
 *   1. Read localStorage cache (fast path) and validate against backend
 *   2. If invalid: GET /stories → create if empty → GET /branches → create if empty
 *   3. Persist {storyId, branchId} to localStorage keyed by clerk userId
 *
 * The active branch concept: Story.active_branch_id can be null (the backend
 * doesn't auto-set it on story creation, and there's no API to set it).
 * The frontend manages "active branch" itself via this context + localStorage.
 */

import React, { createContext, useContext, useEffect, useState } from 'react'
import { useApiClient } from '@/lib/use-api-client'
import { useUserId } from '@/lib/auth-client'
import type { Story, Branch } from '@/lib/types'

interface StoryContextValue {
  storyId: string | null
  branchId: string | null
  storyTitle: string | null
  branchName: string | null
  isLoading: boolean
  error: string | null
}

const StoryContext = createContext<StoryContextValue>({
  storyId: null,
  branchId: null,
  storyTitle: null,
  branchName: null,
  isLoading: true,
  error: null,
})

const CACHE_KEY_PREFIX = 'ampersand:story-context:'

function readCache(userId: string): { storyId: string; branchId: string } | null {
  try {
    const raw = localStorage.getItem(CACHE_KEY_PREFIX + userId)
    if (!raw) return null
    const parsed = JSON.parse(raw)
    // Defensive: validate shape — old/corrupt entries return null
    if (typeof parsed?.storyId === 'string' && typeof parsed?.branchId === 'string') {
      return parsed
    }
    return null
  } catch {
    return null
  }
}

function writeCache(userId: string, data: { storyId: string; branchId: string }) {
  try {
    localStorage.setItem(CACHE_KEY_PREFIX + userId, JSON.stringify(data))
  } catch {
    // localStorage may be unavailable (private browsing, quota exceeded) — non-fatal
  }
}

export function StoryProvider({ children }: { children: React.ReactNode }) {
  const apiClient = useApiClient()
  const userId = useUserId()

  const [value, setValue] = useState<StoryContextValue>({
    storyId: null,
    branchId: null,
    storyTitle: null,
    branchName: null,
    isLoading: true,
    error: null,
  })

  useEffect(() => {
    if (!userId) return
    let cancelled = false

    async function bootstrap() {
      try {
        // 1. Fast path: validate localStorage cache against backend
        const cached = readCache(userId!)
        if (cached) {
          const stories = (await apiClient.listStories()) as Story[]
          if (cancelled) return
          const cachedStory = stories.find((s) => s.id === cached.storyId)
          if (cachedStory) {
            const branches = (await apiClient.listBranches(cached.storyId)) as Branch[]
            if (cancelled) return
            const cachedBranch = branches.find((b) => b.id === cached.branchId)
            if (cachedBranch) {
              setValue({
                storyId: cached.storyId,
                branchId: cached.branchId,
                storyTitle: cachedStory.title,
                branchName: cachedBranch.name,
                isLoading: false,
                error: null,
              })
              return
            }
          }
          // Cache invalid — fall through to full bootstrap
        }

        // 2. Full bootstrap: list / create story
        let stories = (await apiClient.listStories()) as Story[]
        if (cancelled) return
        if (stories.length === 0) {
          await apiClient.createStory({ title: 'My Story' })
          if (cancelled) return
          stories = (await apiClient.listStories()) as Story[]
          if (cancelled) return
        }
        const story = stories[0]

        // 3. List / create branch (prefer an active one if multiple exist)
        const branches = (await apiClient.listBranches(story.id)) as Branch[]
        if (cancelled) return
        let branch: Branch
        if (branches.length === 0) {
          branch = (await apiClient.createBranch({
            story_id: story.id,
            name: 'Main',
          })) as Branch
          if (cancelled) return
        } else {
          branch = branches.find((b) => b.state === 'active') ?? branches[0]
        }

        // 4. Persist + expose
        writeCache(userId!, { storyId: story.id, branchId: branch.id })
        setValue({
          storyId: story.id,
          branchId: branch.id,
          storyTitle: story.title,
          branchName: branch.name,
          isLoading: false,
          error: null,
        })
      } catch (err) {
        if (!cancelled) {
          setValue((prev) => ({
            ...prev,
            isLoading: false,
            error: err instanceof Error ? err.message : 'Failed to load story',
          }))
        }
      }
    }

    bootstrap()
    return () => {
      cancelled = true
    }
  }, [userId, apiClient])

  return <StoryContext.Provider value={value}>{children}</StoryContext.Provider>
}

export function useStory(): StoryContextValue {
  return useContext(StoryContext)
}
