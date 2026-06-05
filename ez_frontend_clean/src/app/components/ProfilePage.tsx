import { useEffect, useState } from 'react';
import { ArrowLeft, MessageSquare, Clock, TrendingUp } from 'lucide-react';
import { listProjects } from '../../lib/api-client';
import type { Project } from '../../lib/types';

export function ProfilePage({ onNavigateBack, onNavigateStory }: { onNavigateBack: () => void; onNavigateStory: () => void }) {
  const [stories, setStories] = useState<Project[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listProjects()
      .then(setStories)
      .catch((err) => {
        console.error('Failed to load projects:', err);
        setError('Could not load stories. Is the backend running?');
      })
      .finally(() => setIsLoading(false));
  }, []);

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
            <p className="text-4xl mt-2">{stories.length * 10}</p>
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
            <p className="text-4xl mt-2">{stories.length}</p>
          </div>
        </div>

        {/* Error banner */}
        {error && (
          <div className="mb-6 px-4 py-3 rounded-lg bg-red-100 border border-red-300 text-red-700 text-sm">
            {error}
          </div>
        )}

        {/* Stories list */}
        <div>
          <h2 className="text-3xl mb-6">Recent Conversations</h2>

          {isLoading ? (
            <div className="flex items-center justify-center py-24 text-muted-foreground">
              Loading stories...
            </div>
          ) : stories.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-24 text-center">
              <MessageSquare className="w-12 h-12 text-muted-foreground mb-4" />
              <h3 className="mb-2">No stories yet</h3>
              <p className="text-sm text-muted-foreground">
                Start a conversation to create your first story.
              </p>
            </div>
          ) : (
            <div className="space-y-4">
              {stories.map((story) => (
                <button
                  key={story.id}
                  onClick={onNavigateStory}
                  className="w-full bg-card border border-border rounded-xl p-6 hover:border-primary transition-colors text-left"
                >
                  <div className="flex items-start justify-between mb-3">
                    <h3 className="text-xl">{story.title}</h3>
                    <span className="text-sm text-muted-foreground">
                      {new Date(story.created_at).toLocaleDateString(undefined, {
                        month: 'short',
                        day: 'numeric',
                        year: 'numeric',
                      })}
                    </span>
                  </div>
                  <div className="flex items-center gap-2 text-sm text-muted-foreground">
                    <MessageSquare className="w-4 h-4" />
                    <span>{story.primary_branch_id ? 'Active branch' : 'No branches yet'}</span>
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}