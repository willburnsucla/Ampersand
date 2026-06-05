import { useEffect, useRef, useState } from 'react';
import { User, Send, Sparkles, BookOpen, GitBranch } from 'lucide-react';
import { getOrCreateSession, listBeats, sendTurn } from '../../lib/api-client';
import type { Beat } from '../../lib/types';
import { BeatGraph } from './BeatGraph';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
}

const examplePrompts = [
  "Write a mystery story set in a Victorian mansion",
  "Develop a character with a complex backstory",
  "Create a plot outline for a sci-fi adventure",
  "Help me brainstorm themes for my fantasy novel",
  "Analyze the pacing of my current chapter",
];

export function ChatPage({ onNavigateProfile }: { onNavigateProfile: () => void }) {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: '1',
      role: 'assistant',
      content: 'Welcome to Ampersand. I\'m here to help bring your stories to life. What would you like to create today?',
      timestamp: new Date(),
    },
  ]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [beats, setBeats] = useState<Beat[]>([]);

  const sessionRef = useRef<{ projectId: string; branchId: string } | null>(null);
  const isSendingRef = useRef(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const refreshBeats = async (session: { projectId: string; branchId: string }) => {
    try {
      const fetched = await listBeats(session.projectId, session.branchId);
      setBeats(fetched);
    } catch (err) {
      console.error('Failed to fetch beats:', err);
    }
  };

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  useEffect(() => {
    getOrCreateSession('My Ampersand Story')
      .then((session) => {
        sessionRef.current = session;
        return refreshBeats(session);
      })
      .catch((err) => {
        console.error('Failed to create session:', err);
        setError('Could not connect to the backend. Is the server running?');
      });
  }, []);

  const handleSend = async (messageText?: string) => {
    const textToSend = messageText || input;
    if (!textToSend.trim() || isLoading || isSendingRef.current) return;
    if (!sessionRef.current) {
      setError('Session not ready yet — please wait a moment.');
      return;
    }

    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: textToSend,
      timestamp: new Date(),
    };

    isSendingRef.current = true;
    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setIsLoading(true);
    setError(null);

    try {
      const result = await sendTurn({
        project_id: sessionRef.current.projectId,
        branch_id: sessionRef.current.branchId,
        content: textToSend,
      });

      const aiMessage: Message = {
        id: Date.now().toString(),
        role: 'assistant',
        content: result.reply,
        timestamp: new Date(),
      };

      setMessages(prev => [...prev, aiMessage]);

      if (sessionRef.current) {
        await refreshBeats(sessionRef.current);
      }
    } catch (err) {
      console.error('Turn failed:', err);
      setError('Failed to get a response. Please try again.');
    } finally {
      setIsLoading(false);
      isSendingRef.current = false;
    }
  };

  return (
    <div className="flex h-screen bg-background">
      {/* Main Chat Area */}
      <div className="flex flex-col flex-1 min-w-0">
        {/* Header */}
        <header className="border-b border-border bg-card px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2">
              <BookOpen className="w-6 h-6 text-primary" />
              <h1 className="text-3xl">Ampersand</h1>
            </div>
          </div>
          <button
            onClick={onNavigateProfile}
            className="flex items-center gap-2 px-4 py-2 rounded-lg bg-secondary hover:bg-accent transition-colors"
          >
            <User className="w-4 h-4" />
            <span>Profile</span>
          </button>
        </header>

        {/* Error banner */}
        {error && (
          <div className="mx-6 mt-4 px-4 py-3 rounded-lg bg-red-100 border border-red-300 text-red-700 text-sm">
            {error}
          </div>
        )}

        {/* Chat Messages */}
        <div className="flex-1 overflow-y-auto px-6 py-8 space-y-6">
          {messages.map((message) => (
            <div
              key={message.id}
              className={`flex gap-4 ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              {message.role === 'assistant' && (
                <div className="w-10 h-10 rounded-full bg-primary flex items-center justify-center flex-shrink-0">
                  <Sparkles className="w-5 h-5 text-primary-foreground" />
                </div>
              )}
              <div
                className={`w-full px-6 py-4 rounded-2xl ${
                  message.role === 'user'
                    ? 'bg-primary text-primary-foreground'
                    : 'bg-card border border-border'
                }`}
              >
                <p className="leading-relaxed">{message.content}</p>
              </div>
              {message.role === 'user' && (
                <div className="w-10 h-10 rounded-full bg-accent flex items-center justify-center flex-shrink-0">
                  <User className="w-5 h-5 text-accent-foreground" />
                </div>
              )}
            </div>
          ))}

          {/* Typing indicator */}
          {isLoading && (
            <div className="flex gap-4 justify-start">
              <div className="w-10 h-10 rounded-full bg-primary flex items-center justify-center flex-shrink-0">
                <Sparkles className="w-5 h-5 text-primary-foreground" />
              </div>
              <div className="px-6 py-4 rounded-2xl bg-card border border-border">
                <p className="text-muted-foreground animate-pulse">Thinking...</p>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />

          {/* Example Prompts - Show only at start */}
          {messages.length <= 1 && !isLoading && (
            <div className="w-full space-y-4">
              <p className="text-muted-foreground text-center mb-4">Try one of these prompts to get started:</p>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {examplePrompts.map((prompt, index) => (
                  <button
                    key={index}
                    onClick={() => handleSend(prompt)}
                    disabled={isLoading}
                    className="px-5 py-3 rounded-xl bg-card border border-border hover:border-primary hover:bg-secondary transition-all text-left disabled:opacity-50"
                  >
                    <p className="text-sm">{prompt}</p>
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Input Area */}
        <div className="border-t border-border bg-card px-6 py-6">
          <div className="w-full flex gap-4">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter')  handleSend();
                if (e.key === 'Escape') setInput('');
              }}
              placeholder="Tell me about your story idea..."
              disabled={isLoading}
              className="flex-1 px-6 py-4 rounded-xl bg-input-background border border-border focus:outline-none focus:ring-2 focus:ring-ring disabled:opacity-50"
            />
            <button
              onClick={() => handleSend()}
              disabled={isLoading || !input.trim()}
              className="px-6 py-4 rounded-xl bg-primary text-primary-foreground hover:opacity-90 transition-opacity flex items-center gap-2 disabled:opacity-50"
            >
              <Send className="w-5 h-5" />
              <span>Send</span>
            </button>
          </div>
        </div>
      </div>

      {/* Sidebar */}
      <div className="w-96 border-l border-border bg-card flex flex-col">

        {/* Story Graph — takes all available vertical space */}
        <div className="flex flex-col flex-1 min-h-0">
          <div className="px-4 py-3 border-b border-border flex items-center justify-between flex-shrink-0">
            <div className="flex items-center gap-2">
              <GitBranch className="w-4 h-4 text-primary" />
              <span className="font-semibold text-sm">Story Graph</span>
            </div>
            {beats.length > 0 && (
              <span className="text-xs bg-primary/10 text-primary px-2 py-0.5 rounded-full font-medium">
                {beats.length} beat{beats.length !== 1 ? 's' : ''}
              </span>
            )}
          </div>
          <div className="flex-1 overflow-y-auto pt-4">
            <BeatGraph beats={beats} />
          </div>
        </div>

        {/* Stats — compact fixed panel at the bottom */}
        <div className="border-t border-border p-4 flex-shrink-0 space-y-3">
          <div className="grid grid-cols-3 gap-2">
            <div className="rounded-lg bg-secondary/50 p-2 text-center">
              <p className="text-lg font-semibold leading-none">{beats.length}</p>
              <p className="text-[10px] text-muted-foreground mt-1">Beats</p>
            </div>
            <div className="rounded-lg bg-secondary/50 p-2 text-center">
              <p className="text-lg font-semibold leading-none">{Math.max(0, Math.floor((messages.length - 1) / 2))}</p>
              <p className="text-[10px] text-muted-foreground mt-1">Turns</p>
            </div>
            <div className="rounded-lg bg-secondary/50 p-2 text-center">
              <p className="text-lg font-semibold leading-none">{messages.length}</p>
              <p className="text-[10px] text-muted-foreground mt-1">Messages</p>
            </div>
          </div>

          {messages.findLast(m => m.role === 'assistant') && (
            <div className="border-l-2 border-primary pl-3">
              <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wide mb-1">
                Latest response
              </p>
              <p className="text-xs text-muted-foreground line-clamp-3 leading-relaxed">
                {messages.findLast(m => m.role === 'assistant')?.content}
              </p>
            </div>
          )}
        </div>

      </div>
    </div>
  );
}