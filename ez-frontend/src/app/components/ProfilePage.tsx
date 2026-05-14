import { ArrowLeft, MessageSquare, Clock, TrendingUp } from 'lucide-react';

interface PastChat {
  id: string;
  title: string;
  preview: string;
  timestamp: string;
  messageCount: number;
}

const mockChats: PastChat[] = [
  {
    id: '1',
    title: 'The Midnight Garden',
    preview: 'A story about a mysterious garden that only appears at night...',
    timestamp: '2 hours ago',
    messageCount: 24,
  },
  {
    id: '2',
    title: 'Character Development - Sarah',
    preview: 'Working on backstory and motivations for the protagonist...',
    timestamp: 'Yesterday',
    messageCount: 18,
  },
  {
    id: '3',
    title: 'Plot Structure Discussion',
    preview: 'Three-act structure for the sci-fi novella...',
    timestamp: '3 days ago',
    messageCount: 31,
  },
  {
    id: '4',
    title: 'Worldbuilding: Nebula City',
    preview: 'Creating the setting for a cyberpunk thriller...',
    timestamp: 'Last week',
    messageCount: 42,
  },
];

export function ProfilePage({ onNavigateBack, onNavigateStory }: { onNavigateBack: () => void; onNavigateStory: () => void }) {
  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b border-border bg-card px-6 py-4">
        <div className="max-w-6xl mx-auto">
          <button
            onClick={onNavigateBack}
            className="flex items-center gap-2 text-muted-foreground hover:text-foreground transition-colors mb-4"
          >
            <ArrowLeft className="w-4 h-4" />
            <span>Back to Chat</span>
          </button>
          <h1 className="text-4xl">Your Writing Journey</h1>
        </div>
      </header>

      <div className="max-w-6xl mx-auto px-6 py-8">
        {/* Stats */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-12">
          <div className="bg-card border border-border rounded-xl p-6">
            <div className="flex items-center gap-3 mb-2">
              <MessageSquare className="w-5 h-5 text-primary" />
              <h3>Total Conversations</h3>
            </div>
            <p className="text-4xl mt-2">127</p>
          </div>
          <div className="bg-card border border-border rounded-xl p-6">
            <div className="flex items-center gap-3 mb-2">
              <Clock className="w-5 h-5 text-primary" />
              <h3>Hours Writing</h3>
            </div>
            <p className="text-4xl mt-2">48</p>
          </div>
          <div className="bg-card border border-border rounded-xl p-6">
            <div className="flex items-center gap-3 mb-2">
              <TrendingUp className="w-5 h-5 text-primary" />
              <h3>Stories Created</h3>
            </div>
            <p className="text-4xl mt-2">12</p>
          </div>
        </div>

        {/* Past Chats */}
        <div>
          <h2 className="text-3xl mb-6">Recent Conversations</h2>
          <div className="space-y-4">
            {mockChats.map((chat) => (
              <button
                key={chat.id}
                onClick={onNavigateStory}
                className="w-full bg-card border border-border rounded-xl p-6 hover:border-primary transition-colors text-left"
              >
                <div className="flex items-start justify-between mb-3">
                  <h3 className="text-xl">{chat.title}</h3>
                  <span className="text-sm text-muted-foreground">{chat.timestamp}</span>
                </div>
                <p className="text-muted-foreground mb-3">{chat.preview}</p>
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <MessageSquare className="w-4 h-4" />
                  <span>{chat.messageCount} messages</span>
                </div>
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

/**
 * TODO once backend has endpoints:
 * 11–40
mockChats — fake past conversations
GET /chats or GET /users/me/conversations
89–105
Renders mockChats; onNavigateStory ignores which chat was clicked
Pass chat.id into route/state and load that story
67, 74, 81
Stats 127, 48, 12
GET /users/me/stats or aggregates from backend
 */