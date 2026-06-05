/**
 * ConversationStore — Zustand slice for conversation history per (storyId, branchId).
 *
 * Why not local state in ChatPane: the component unmounts on nav (e.g. user
 * clicks Inspector then Conversation again). Local state would lose history.
 * Putting it in Zustand keeps it across navigations within the same session.
 *
 * In-memory only within a tab session. On mount, ChatPane hydrates from the
 * backend via listTurns so history survives page refreshes.
 */

import { create } from 'zustand'

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
}

interface ConversationStoreState {
  // Keyed by `${storyId}:${branchId}` so switching branches shows the right history
  messagesByContext: Record<string, ChatMessage[]>

  appendMessage: (storyId: string, branchId: string, message: ChatMessage) => void
  setMessages: (storyId: string, branchId: string, messages: ChatMessage[]) => void
  clearContext: (storyId: string, branchId: string) => void
  reset: () => void
}

function contextKey(storyId: string, branchId: string) {
  return `${storyId}:${branchId}`
}

export const useConversationStore = create<ConversationStoreState>((set) => ({
  messagesByContext: {},

  appendMessage(storyId, branchId, message) {
    set((state) => {
      const key = contextKey(storyId, branchId)
      const existing = state.messagesByContext[key] ?? []
      return {
        messagesByContext: {
          ...state.messagesByContext,
          [key]: [...existing, message],
        },
      }
    })
  },

  setMessages(storyId, branchId, messages) {
    set((state) => ({
      messagesByContext: {
        ...state.messagesByContext,
        [contextKey(storyId, branchId)]: messages,
      },
    }))
  },

  clearContext(storyId, branchId) {
    set((state) => {
      const next = { ...state.messagesByContext }
      delete next[contextKey(storyId, branchId)]
      return { messagesByContext: next }
    })
  },

  reset() {
    set({ messagesByContext: {} })
  },
}))

export function useMessages(storyId: string | null, branchId: string | null): ChatMessage[] {
  return useConversationStore((s) => {
    if (!storyId || !branchId) return EMPTY
    return s.messagesByContext[contextKey(storyId, branchId)] ?? EMPTY
  })
}

// Stable empty array to avoid causing re-renders when no messages exist
const EMPTY: ChatMessage[] = []
