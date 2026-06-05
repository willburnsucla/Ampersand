'use client'

import { useState, useRef, useEffect } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useApiClient } from '@/lib/use-api-client'
import { useConversationStore, useMessages, type ChatMessage } from '@/lib/conversation-store'
import type { TurnResultV2 } from '@/lib/types'

interface ChatPaneProps {
  storyId: string   // v2 project_id
  branchId: string
}

export function ChatPane({ storyId, branchId }: ChatPaneProps) {
  const apiClient = useApiClient()
  const queryClient = useQueryClient()
  const messages = useMessages(storyId, branchId)
  const appendMessage = useConversationStore((s) => s.appendMessage)
  const setMessages = useConversationStore((s) => s.setMessages)
  const [input, setInput] = useState('')
  const bottomRef = useRef<HTMLDivElement>(null)

  // Hydrate conversation history from backend on mount
  useQuery({
    queryKey: ['turns', storyId, branchId],
    queryFn: async () => {
      const turns = await apiClient.listTurns(storyId, branchId)
      const chatMessages: ChatMessage[] = turns.map((t) => ({
        id: t.id,
        role: t.role === 'writer' ? 'user' : 'assistant',
        content: t.content,
      }))
      setMessages(storyId, branchId, chatMessages)
      return turns
    },
    enabled: !!storyId && !!branchId,
    // Only hydrate once per session — in-memory store takes over after
    staleTime: Infinity,
  })

  const mutation = useMutation({
    mutationFn: async (content: string): Promise<TurnResultV2> => {
      return apiClient.postTurnV2({ project_id: storyId, branch_id: branchId, content })
    },
    onSuccess: (data) => {
      appendMessage(storyId, branchId, {
        id: `assistant-${Date.now()}`,
        role: 'assistant',
        content: data.reply || '(empty reply)',
      })
      // Refresh entity queries so Inspector updates after each turn
      queryClient.invalidateQueries({ queryKey: ['beats', storyId, branchId] })
      queryClient.invalidateQueries({ queryKey: ['characters', storyId] })
      queryClient.invalidateQueries({ queryKey: ['themes', storyId] })
      queryClient.invalidateQueries({ queryKey: ['settings', storyId] })
    },
  })

  // Auto-scroll on new messages or while thinking
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, mutation.isPending])

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    const content = input.trim()
    if (!content || mutation.isPending) return

    const userId =
      typeof crypto !== 'undefined' && 'randomUUID' in crypto
        ? `user-${crypto.randomUUID()}`
        : `user-${Date.now()}-${Math.random().toString(36).slice(2)}`

    appendMessage(storyId, branchId, { id: userId, role: 'user', content })
    setInput('')
    mutation.mutate(content)
  }

  return (
    <div className="flex flex-col h-full">
      {/* Message list */}
      <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
        {messages.length === 0 && !mutation.isPending && (
          <p className="text-sm text-foreground/40 text-center mt-12">
            Start writing your story. Tell Ampersand about your characters, setting, or first scene.
          </p>
        )}
        {messages.map((msg) => (
          <MessageBubble key={msg.id} message={msg} />
        ))}
        {mutation.isPending && <ThinkingIndicator />}
        {mutation.isError && (
          <p className="text-sm text-red-500 text-center">
            {mutation.error instanceof Error ? mutation.error.message : 'Something went wrong'}
          </p>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <form
        onSubmit={handleSubmit}
        className="border-t border-border px-6 py-4 flex gap-3 items-end"
      >
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault()
              handleSubmit(e as unknown as React.FormEvent)
            }
          }}
          placeholder="Describe your story…"
          rows={2}
          disabled={mutation.isPending}
          className="flex-1 resize-none rounded-md border border-border bg-background px-3 py-2 text-sm
                     placeholder:text-foreground/40 focus:outline-none focus:ring-1 focus:ring-foreground/20
                     disabled:opacity-50 transition-opacity"
        />
        <button
          type="submit"
          disabled={mutation.isPending || !input.trim()}
          className="px-4 py-2 rounded-md bg-foreground text-background text-sm font-medium
                     hover:bg-foreground/90 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          Send
        </button>
      </form>
    </div>
  )
}

function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === 'user'
  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div
        className={`max-w-[80%] rounded-lg px-4 py-2.5 text-sm whitespace-pre-wrap leading-relaxed
          ${isUser
            ? 'bg-foreground text-background'
            : 'bg-foreground/5 text-foreground border border-border'
          }`}
      >
        {message.content}
      </div>
    </div>
  )
}

function ThinkingIndicator() {
  return (
    <div className="flex justify-start">
      <div className="bg-foreground/5 border border-border rounded-lg px-4 py-3 flex items-center gap-1.5">
        {[0, 1, 2].map((i) => (
          <span
            key={i}
            className="inline-block w-1.5 h-1.5 rounded-full bg-foreground/40 animate-bounce"
            style={{ animationDelay: `${i * 0.15}s` }}
          />
        ))}
      </div>
    </div>
  )
}
