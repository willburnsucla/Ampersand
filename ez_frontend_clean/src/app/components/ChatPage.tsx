import { useEffect, useRef, useState } from 'react';
import { User, Send, Sparkles, BookOpen, BarChart3, GitBranch, TrendingUp, Users } from 'lucide-react';
import { LineChart, Line, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar, XAxis, YAxis, CartesianGrid, ResponsiveContainer } from 'recharts';
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

const mockPaceData = [
  { point: '1', tension: 65 },
  { point: '2', tension: 72 },
  { point: '3', tension: 85 },
  { point: '4', tension: 78 },
];

const mockCharacterData = [
  { subject: 'Depth', value: 75 },
  { subject: 'Voice', value: 82 },
  { subject: 'Arc', value: 70 },
  { subject: 'Motivation', value: 78 },
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
  const [hasEnoughData, setHasEnoughData] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [beats, setBeats] = useState<Beat[]>([]);

  const sessionRef = useRef<{ projectId: string; branchId: string } | null>(null);
  const isSendingRef = useRef(false);

  const refreshBeats = async (session: { projectId: string; branchId: string }) => {
    try {
      const fetched = await listBeats(session.projectId, session.branchId);
      setBeats(fetched);
    } catch (err) {
      console.error('Failed to fetch beats:', err);
    }
  };

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

      setMessages(prev => {
        const updated = [...prev, aiMessage];
        if (updated.length >= 6) setHasEnoughData(true);
        return updated;
      });

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
              onKeyDown={(e) => e.key === 'Enter' && handleSend()}
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

      {/* Sidebar - Real-time Visuals */}
      <div className="w-96 border-l border-border bg-card overflow-y-auto">
        {/* Story Graph */}
        <div className="p-6 border-b border-border">
          <div className="flex items-center gap-2 mb-3">
            <GitBranch className="w-5 h-5 text-primary" />
            <h3 className="text-xl">Story Graph</h3>
          </div>
          <BeatGraph beats={beats} />
        </div>

        <div className="p-6 border-b border-border">
          <div className="flex items-center gap-2 mb-2">
            <BarChart3 className="w-5 h-5 text-primary" />
            <h3 className="text-xl">Live Insights</h3>
          </div>
          <p className="text-sm text-muted-foreground">Real-time analysis of your conversation</p>
        </div>

        <div className="p-6 space-y-6">
          {!hasEnoughData ? (
            <div className="flex flex-col items-center justify-center py-12 text-center">
              <div className="w-16 h-16 rounded-full bg-secondary flex items-center justify-center mb-4">
                <Sparkles className="w-8 h-8 text-muted-foreground" />
              </div>
              <h4 className="mb-2">No data yet</h4>
              <p className="text-sm text-muted-foreground max-w-xs">
                Keep chatting about your story and I'll start generating insights and visualizations based on our conversation.
              </p>
            </div>
          ) : (
            <>
              <div>
                <div className="flex items-center gap-2 mb-3">
                  <TrendingUp className="w-4 h-4 text-primary" />
                  <h4>Story Tension</h4>
                </div>
                <ResponsiveContainer width="100%" height={150}>
                  <LineChart data={mockPaceData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                    <XAxis dataKey="point" stroke="var(--muted-foreground)" fontSize={12} />
                    <YAxis stroke="var(--muted-foreground)" fontSize={12} />
                    <Line type="monotone" dataKey="tension" stroke="var(--chart-1)" strokeWidth={2} dot={{ r: 4 }} />
                  </LineChart>
                </ResponsiveContainer>
                <p className="text-xs text-muted-foreground mt-2">
                  Tension is building nicely through your plot points
                </p>
              </div>

              <div>
                <div className="flex items-center gap-2 mb-3">
                  <Users className="w-4 h-4 text-primary" />
                  <h4>Character Analysis</h4>
                </div>
                <ResponsiveContainer width="100%" height={150}>
                  <RadarChart data={mockCharacterData}>
                    <PolarGrid stroke="var(--border)" />
                    <PolarAngleAxis dataKey="subject" stroke="var(--muted-foreground)" fontSize={10} />
                    <PolarRadiusAxis stroke="var(--muted-foreground)" fontSize={10} />
                    <Radar dataKey="value" stroke="var(--chart-1)" fill="var(--chart-1)" fillOpacity={0.3} />
                  </RadarChart>
                </ResponsiveContainer>
                <p className="text-xs text-muted-foreground mt-2">
                  Your protagonist shows strong character voice
                </p>
              </div>

              <div className="space-y-3">
                <h4>Session Stats</h4>
                <div className="space-y-2">
                  <div className="flex justify-between items-center p-3 rounded-lg bg-secondary/50">
                    <span className="text-sm">Messages</span>
                    <span className="font-medium">{messages.length}</span>
                  </div>
                  <div className="flex justify-between items-center p-3 rounded-lg bg-secondary/50">
                    <span className="text-sm">Topics Discussed</span>
                    <span className="font-medium">{Math.floor(messages.length / 2)}</span>
                  </div>
                  <div className="flex justify-between items-center p-3 rounded-lg bg-secondary/50">
                    <span className="text-sm">Story Elements</span>
                    <span className="font-medium">{Math.max(1, messages.length - 2)}</span>
                  </div>
                </div>
              </div>

              <div className="border-l-4 border-primary pl-4">
                <h4 className="mb-2 text-sm">Latest Insight</h4>
                <p className="text-sm text-muted-foreground">
                  {messages.findLast(m => m.role === 'assistant')?.content ?? 'Keep writing to generate insights.'}
                </p>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}