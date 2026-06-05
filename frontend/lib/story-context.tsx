'use client'

/**
 * StoryContext — bootstraps the active project + branch on mount using v2 APIs.
 *
 * Bootstrap sequence:
 *   1. Read localStorage cache (fast path) and validate against backend
 *   2. If invalid: GET /api/v2/projects → create if empty → GET branches → create if empty
 *   3. Persist {projectId, branchId} to localStorage keyed by user id
 *
 * storyId in the context value IS the v2 project_id — kept as "storyId" so
 * downstream components (ChatPane, GraphBootstrap) don't need renaming yet.
 */

import React, { createContext, useContext, useEffect, useState } from 'react'
import { useApiClient } from '@/lib/use-api-client'
import { useUserId } from '@/lib/auth-client'
import type { Branch } from '@/lib/types'

interface StoryContextValue {
  storyId: string | null     // v2 project_id
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

const CACHE_KEY_PREFIX = 'ampersand:project-context:'

function readCache(userId: string): { projectId: string; branchId: string } | null {
  try {
    const raw = localStorage.getItem(CACHE_KEY_PREFIX + userId)
    if (!raw) return null
    const parsed = JSON.parse(raw)
    if (typeof parsed?.projectId === 'string' && typeof parsed?.branchId === 'string') {
      return parsed
    }
    return null
  } catch {
    return null
  }
}

function writeCache(userId: string, data: { projectId: string; branchId: string }) {
  try {
    localStorage.setItem(CACHE_KEY_PREFIX + userId, JSON.stringify(data))
  } catch {}
}

function clearCache(userId: string) {
  try {
    localStorage.removeItem(CACHE_KEY_PREFIX + userId)
  } catch {}
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
          const projects = await apiClient.listProjects()
          if (cancelled) return
          const cachedProject = projects.find((p) => p.id === cached.projectId)
          if (cachedProject) {
            const branches = await apiClient.listBranchesV2(cached.projectId)
            if (cancelled) return
            const cachedBranch = branches.find((b) => b.id === cached.branchId)
            if (cachedBranch) {
              setValue({
                storyId: cached.projectId,
                branchId: cached.branchId,
                storyTitle: cachedProject.title,
                branchName: cachedBranch.name,
                isLoading: false,
                error: null,
              })
              return
            }
          }
          // Cache invalid — clear it and fall through to full bootstrap
          clearCache(userId!)
        }

        // 2. Full bootstrap: list / create project
        let projects = await apiClient.listProjects()
        if (cancelled) return
        if (projects.length === 0) {
          await apiClient.createProject({ title: 'My Story' })
          if (cancelled) return
          projects = await apiClient.listProjects()
          if (cancelled) return
        }
        const project = projects[0]

        // 3. List / create branch (prefer an active one)
        const branches = await apiClient.listBranchesV2(project.id)
        if (cancelled) return
        let branch: Branch
        if (branches.length === 0) {
          branch = await apiClient.createBranchV2({ project_id: project.id, name: 'Main' })
          if (cancelled) return
        } else {
          branch = branches.find((b) => b.state === 'active') ?? branches[0]
        }

        // 4. Persist + expose
        writeCache(userId!, { projectId: project.id, branchId: branch.id })
        setValue({
          storyId: project.id,
          branchId: branch.id,
          storyTitle: project.title,
          branchName: branch.name,
          isLoading: false,
          error: null,
        })
      } catch (err) {
        if (!cancelled) {
          setValue((prev) => ({
            ...prev,
            isLoading: false,
            error: err instanceof Error ? err.message : 'Failed to load project',
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
