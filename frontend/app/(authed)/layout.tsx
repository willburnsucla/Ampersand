'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { useUserId } from '@/lib/auth-client'
import { StoryProvider } from '@/lib/story-context'
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

function AuthedShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex h-screen overflow-hidden bg-background">
      <Sidebar />
      <main className="flex-1 overflow-auto">
        {children}
      </main>
    </div>
  )
}
