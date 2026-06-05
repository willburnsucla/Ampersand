import { useEffect, useRef, useState } from 'react';
import { User, Send, Sparkles, BookOpen, GitBranch, LogOut, Check } from 'lucide-react';
import { deleteBeat, forkBranch, getOrCreateSession, listBeats, listBranches, sendTurn, setBeatStatus } from '../../lib/api-client';
import { useAuth } from '../../lib/auth';
import type { Beat, Branch } from '../../lib/types';
import { BeatGraph } from './BeatGraph';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
}

const examplePrompts = [
  "Luke buys two droids on Tatooine. R2-D2 plays a message from Princess Leia. Luke seeks out old Ben Kenobi.",
  "Maya the detective steps into the dark forest, hunting her sister's killer.",
  "The old wizard reaches the castle gates at midnight, carrying a sealed letter.",
  "Two ships meet in the harbor at dawn, one carrying a dangerous secret.",
];

export function ChatPage({ onNavigateProfile, projectId }: { onNavigateProfile: () => void; projectId?: string }) {
  const { signOut } = useAuth();
  const [messages, setMessages] = useState<Message[]>([
    {
      id: '1',
      role: 'assistant',
      content: 'Welcome to Ampersand. Paste your writing and I\'ll organize it into beats and a story graph. I structure what you wrote, I don\'t write it for you.',
      timestamp: new Date(),
    },
  ]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [beats, setBeats] = useState<Beat[]>([]);
  const [branches, setBranches] = useState<Branch[]>([]);
  const [activeBranchId, setActiveBranchId] = useState<string | null>(null);
  const [forking, setForking] = useState(false);

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

  const refreshBranches = async (projectId: string) => {
    try {
      setBranches(await listBranches(projectId));
    } catch (err) {
      console.error('Failed to fetch branches:', err);
    }
  };

  const switchBranch = async (branchId: string) => {
    if (!sessionRef.current || branchId === sessionRef.current.branchId) return;
    sessionRef.current = { ...sessionRef.current, branchId };
    setActiveBranchId(branchId);
    await refreshBeats(sessionRef.current);
  };

  const handleFork = async () => {
    if (!sessionRef.current || forking || beats.length === 0) return;
    setForking(true);
    try {
      const lastBeat = beats[beats.length - 1];
      const created = await forkBranch({
        project_id: sessionRef.current.projectId,
        parent_branch_id: sessionRef.current.branchId,
        from_beat_id: lastBeat.id,
        name: `alt ${branches.length}`,
      });
      await refreshBranches(sessionRef.current.projectId);
      await switchBranch(created.id);
    } catch (err) {
      console.error('Fork failed:', err);
      setError('Could not fork a new branch.');
    } finally {
      setForking(false);
    }
  };

  const handleDeleteBeat = async (beatId: string) => {
    if (!sessionRef.current) return;
    const session = sessionRef.current;
    try {
      await deleteBeat(session.projectId, session.branchId, beatId);
    } catch (err) {
      console.error('Delete beat failed:', err);
      setError('Could not delete that beat.');
    }
    await refreshBeats(session);  // resync either way, so a failed delete puts the beat back
  };

  const handleCommitBeat = async (beatId: string) => {
    if (!sessionRef.current) return;
    const session = sessionRef.current;
    try {
      await setBeatStatus(session.projectId, session.branchId, beatId, 'committed');
    } catch (err) {
      console.error('Commit beat failed:', err);
      setError('Could not commit that beat.');
    }
    await refreshBeats(session);  // resync either way, so a failed commit reverts
  };

  const handleCommitAll = async () => {
    if (!sessionRef.current) return;
    const session = sessionRef.current;
    const proposed = beats.filter(b => b.status === 'proposed');
    if (proposed.length === 0) return;
    try {
      await Promise.all(
        proposed.map(b => setBeatStatus(session.projectId, session.branchId, b.id, 'committed'))
      );
    } catch (err) {
      console.error('Commit all failed:', err);
      setError('Could not commit the proposed beats.');
    }
    await refreshBeats(session);
  };

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  useEffect(() => {
    getOrCreateSession('My Ampersand Story', projectId)
      .then(async (session) => {
        sessionRef.current = session;
        setActiveBranchId(session.branchId);
        await refreshBeats(session);
        await refreshBranches(session.projectId);
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
          <div className="flex items-center gap-2">
            <button
              onClick={onNavigateProfile}
              className="flex items-center gap-2 px-4 py-2 rounded-lg bg-secondary hover:bg-accent transition-colors"
            >
              <User className="w-4 h-4" />
              <span>Profile</span>
            </button>
            <button
              onClick={signOut}
              className="flex items-center gap-2 px-4 py-2 rounded-lg bg-secondary hover:bg-accent transition-colors"
            >
              <LogOut className="w-4 h-4" />
              <span>Sign out</span>
            </button>
          </div>
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
              <p className="text-muted-foreground text-center mb-4">Or try one of these passages to see the beats:</p>
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
          {branches.length > 0 && (
            <div className="px-4 py-2 border-b border-border flex items-center gap-2 flex-shrink-0 overflow-x-auto">
              {branches.map((b) => (
                <button
                  key={b.id}
                  onClick={() => switchBranch(b.id)}
                  className={`text-xs px-2 py-1 rounded-full whitespace-nowrap transition-colors ${
                    b.id === activeBranchId
                      ? 'bg-primary text-primary-foreground'
                      : 'bg-secondary hover:bg-accent'
                  }`}
                >
                  {b.name || 'branch'}
                </button>
              ))}
              <button
                onClick={handleFork}
                disabled={forking || beats.length === 0}
                title="Fork an alternate timeline from the latest beat"
                className="ml-auto text-xs px-2 py-1 rounded-full bg-secondary hover:bg-accent flex items-center gap-1 disabled:opacity-50 whitespace-nowrap"
              >
                <GitBranch className="w-3 h-3" />
                {forking ? 'Forking…' : 'Fork'}
              </button>
            </div>
          )}
          {beats.some(b => b.status === 'proposed') && (
            <button
              onClick={handleCommitAll}
              className="mx-4 mt-3 mb-1 flex items-center justify-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-lg bg-primary/10 text-primary hover:bg-primary/20 transition-colors flex-shrink-0"
            >
              <Check className="w-3.5 h-3.5" />
              Commit all {beats.filter(b => b.status === 'proposed').length} proposed
            </button>
          )}
          <div className="flex-1 overflow-y-auto pt-4">
            <BeatGraph beats={beats} onDeleteBeat={handleDeleteBeat} onCommitBeat={handleCommitBeat} />
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