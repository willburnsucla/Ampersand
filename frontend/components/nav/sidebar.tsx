'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { MessageSquare, Search, BarChart2, GitBranch, Download } from 'lucide-react'
import { clsx } from 'clsx'
import { useStory } from '@/lib/story-context'

const NAV_ITEMS = [
  { label: 'Conversation',   href: '/conversation',   icon: MessageSquare },
  { label: 'Inspector',      href: '/inspector',      icon: Search },
  { label: 'Visualizations', href: '/visualizations', icon: BarChart2 },
  { label: 'Branches',       href: '/branches',       icon: GitBranch },
  { label: 'Export',         href: '/export',         icon: Download },
] as const

export function Sidebar() {
  const pathname = usePathname()
  const { storyTitle, branchName, isLoading } = useStory()

  return (
    <aside className="w-[220px] shrink-0 flex flex-col h-full border-r border-border bg-background">
      {/* Logo */}
      <div className="px-5 py-5 border-b border-border">
        <span className="text-lg font-semibold tracking-tight">Ampersand</span>
      </div>

      {/* Nav links */}
      <nav className="flex-1 px-3 py-4 space-y-1">
        {NAV_ITEMS.map(({ label, href, icon: Icon }) => {
          const isActive = pathname.startsWith(href)
          return (
            <Link
              key={href}
              href={href}
              className={clsx(
                'flex items-center gap-3 px-3 py-2 rounded-md text-sm transition-colors',
                isActive
                  ? 'bg-foreground/10 text-foreground font-medium'
                  : 'text-foreground/60 hover:text-foreground hover:bg-foreground/5',
              )}
            >
              <Icon className="h-4 w-4 shrink-0" />
              {label}
            </Link>
          )
        })}
      </nav>

      {/* Story/branch footer */}
      <div className="px-5 py-4 border-t border-border">
        {isLoading ? (
          <div className="space-y-1.5">
            <div className="h-3 w-24 rounded bg-foreground/10 animate-pulse" />
            <div className="h-3 w-16 rounded bg-foreground/10 animate-pulse" />
          </div>
        ) : (
          <div className="space-y-0.5">
            <p className="text-sm font-medium truncate">{storyTitle ?? '—'}</p>
            <p className="text-xs text-foreground/50 truncate">
              {branchName ?? 'No branch'}
            </p>
          </div>
        )}
      </div>
    </aside>
  )
}
