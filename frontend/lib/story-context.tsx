'use client'

/**
 * StoryContext — bootstraps the active story + branch on mount.
 *
 * Bootstrap sequence:
 * 1. Check localStorage for persisted {storyId, branchId} keyed by userId
 * 2. If not found: GET /stories → create if empty → GET /branches → create if empty
 * 3. Persist result to localStorage for fast subsequent loads
 */

import React, { createContext, useContext, useEffect, useMemo, useState } from 'react'
import { HttpApiClient } from '@/lib/api-client'
import { useGetToken, useUserId } from '@/lib/auth-client'
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

function localKey(userId: string) {
  return `ampersand:story-context:${userId}`
}

function readCache(userId: string): { storyId: string; branchId: string } | null {
  try {
    const raw = localStorage.getItem(localKey(userId))
    if (!raw) return null
    return JSON.parse(raw)
  } catch {
    return null
  }
}

function writeCache(userId: string, data: { storyId: string; branchId: string }) {
  try {
    localStorage.setItem(localKey(userId), JSON.stringify(data))
  } catch {}
}

export function StoryProvider({ children }: { children: React.ReactNode }) {
  const getToken = useGetToken()
  const userId = useUserId()
  const apiClient = useMemo(() => new HttpApiClient(getToken), [getToken])

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
        // 1. Check localStorage cache
        const cached = readCache(userId!)
        if (cached) {
          // Fast-path: try to validate cache by listing stories
          const stories = (await apiClient.listStories()) as Story[]
          const cachedStory = stories.find((s) => s.id === cached.storyId)
          if (cachedStory && !cancelled) {
            const branches = (await apiClient.listBranches(cached.storyId)) as Branch[]
            const cachedBranch = branches.find((b) => b.id === cached.branchId)
            if (cachedBranch && !cancelled) {
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
        }

        // 2. Full bootstrap: list / create story
        let stories = (await apiClient.listStories()) as Story[]
        if (stories.length === 0) {
          await apiClient.createStory({ title: 'My Story' })
          stories = (await apiClient.listStories()) as Story[]
        }
        if (cancelled) return
        const story = stories[0]

        // 3. List / create branch
        const branches = (await apiClient.listBranches(story.id)) as Branch[]
        let branch: Branch
        if (branches.length === 0) {
          branch = (await apiClient.createBranch({ story_id: story.id, name: 'Main' })) as Branch
        } else {
          // Prefer an active branch
          branch = branches.find((b) => b.state === 'active') ?? branches[0]
        }

        if (cancelled) return

        // 4. Persist and expose
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
  }, [apiClient, userId])

  return <StoryContext.Provider value={value}>{children}</StoryContext.Provider>
}

export function useStory(): StoryContextValue {
  return useContext(StoryContext)
}
