'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { useUserId } from '@/lib/auth-client'
import { StoryProvider, useStory } from '@/lib/story-context'
import { useGraphBootstrap } from '@/lib/use-graph-bootstrap'
import { Sidebar } from '@/components/nav/sidebar'

export default function AuthedLayout({ children }: { children: React.ReactNode }) {
  const userId = useUserId()
  const router = useRouter()

  useEffect(() => {
    if (userId === null) router.replace('/sign-in')
  }, [userId, router])

  if (userId === undefined) return null 
  if (userId === null) return null 

  return (
    <StoryProvider>
      <AuthedShell>{children}</AuthedShell>
    </StoryProvider>
  )
}

/**
 * Inner shell — split out so it can call useStory()/useGraphBootstrap()
 * which require StoryProvider as an ancestor.
 */
function AuthedShell({ children }: { children: React.ReactNode }) {
  const { storyId, branchId } = useStory()

  // Bootstrap graph + SSE once per session — keeps Inspector / Visualizations
  // working without requiring the user to visit Conversation first
  useGraphBootstrap(storyId, branchId)

  return (
    <div className="flex h-screen overflow-hidden bg-background">
      <Sidebar />
      <main className="flex-1 overflow-auto">
        {children}
      </main>
    </div>
  )
}
