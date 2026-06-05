import { useEffect, useState } from 'react';
import { ArrowLeft, MessageSquare, BookOpen, TrendingUp, Search, Plus, X, Loader2, Trash2 } from 'lucide-react';
import { listProjects, createProject, createBranch, clearSession, deleteProject } from '../../lib/api-client';
import type { Project } from '../../lib/types';

interface NewStoryFormProps {
  onCancel: () => void;
  onCreate: (project: Project) => void;
}

function NewStoryForm({ onCancel, onCreate }: NewStoryFormProps) {
  const [title, setTitle] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = title.trim();
    if (!trimmed) return;
    setIsSubmitting(true);
    setError(null);
    try {
      const project = await createProject({ title: trimmed });
      await createBranch({ project_id: project.id, name: 'main' });
      onCreate(project);
    } catch {
      setError('Failed to create story. Is the backend running?');
      setIsSubmitting(false);
    }
  };

  return (
    <div className="bg-card border border-primary/40 rounded-xl p-6 mb-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold">New Story</h3>
        <button onClick={onCancel} className="text-muted-foreground hover:text-foreground transition-colors">
          <X className="w-4 h-4" />
        </button>
      </div>
      <form onSubmit={handleSubmit} className="flex gap-3">
        <input
          autoFocus
          type="text"
          placeholder="Story title…"
          value={title}
          onChange={e => setTitle(e.target.value)}
          onKeyDown={e => e.key === 'Escape' && onCancel()}
          disabled={isSubmitting}
          className="flex-1 px-4 py-2 rounded-lg border border-border bg-background focus:outline-none focus:ring-2 focus:ring-ring text-sm disabled:opacity-50"
        />
        <button
          type="submit"
          disabled={isSubmitting || !title.trim()}
          className="px-4 py-2 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:opacity-90 disabled:opacity-40 transition-opacity flex items-center gap-2"
        >
          {isSubmitting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}
          Create
        </button>
      </form>
      {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
    </div>
  );
}

interface ProfilePageProps {
  onNavigateBack: () => void;
  onNavigateStory: (project: Project) => void;
  onStartNewStory: (project: Project) => void;
}

export function ProfilePage({ onNavigateBack, onNavigateStory, onStartNewStory }: ProfilePageProps) {
  const [stories, setStories]         = useState<Project[]>([]);
  const [isLoading, setIsLoading]     = useState(true);
  const [error, setError]             = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [showNewForm, setShowNewForm] = useState(false);

  useEffect(() => {
    listProjects()
      .then(setStories)
      .catch(() => setError('Could not load stories. Is the backend running?'))
      .finally(() => setIsLoading(false));
  }, []);

  const filteredStories = stories.filter(s =>
    s.title.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const handleNewStoryCreated = (project: Project) => {
    setStories(prev => [project, ...prev]);
    setShowNewForm(false);
    clearSession();
    onStartNewStory(project);
  };

  const handleDelete = async (e: React.MouseEvent, projectId: string) => {
    e.stopPropagation();
    if (!confirm('Delete this story? This cannot be undone.')) return;
    try {
      await deleteProject(projectId);
      setStories(prev => prev.filter(s => s.id !== projectId));
    } catch {
      setError('Failed to delete story.');
    }
  };

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
          <div className="flex items-center justify-between">
            <h1 className="text-4xl">Your Writing Journey</h1>
            <button
              onClick={() => setShowNewForm(v => !v)}
              className="flex items-center gap-2 px-4 py-2 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:opacity-90 transition-opacity"
            >
              <Plus className="w-4 h-4" />
              New Story
            </button>
          </div>
        </div>
      </header>

      <div className="max-w-6xl mx-auto px-6 py-8">
        {/* Stats */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-10">
          <div className="bg-card border border-border rounded-xl p-6">
            <div className="flex items-center gap-3 mb-2">
              <BookOpen className="w-5 h-5 text-primary" />
              <h3>Stories Created</h3>
            </div>
            <p className="text-4xl mt-2">{stories.length}</p>
          </div>
          <div className="bg-card border border-border rounded-xl p-6">
            <div className="flex items-center gap-3 mb-2">
              <MessageSquare className="w-5 h-5 text-primary" />
              <h3>Active Stories</h3>
            </div>
            <p className="text-4xl mt-2">
              {stories.filter(s => s.primary_branch_id !== null).length}
            </p>
          </div>
          <div className="bg-card border border-border rounded-xl p-6">
            <div className="flex items-center gap-3 mb-2">
              <TrendingUp className="w-5 h-5 text-primary" />
              <h3>This Session</h3>
            </div>
            <p className="text-4xl mt-2">
              {stories.filter(s => {
                const created = new Date(s.created_at);
                const cutoff  = new Date(Date.now() - 24 * 60 * 60 * 1000);
                return created > cutoff;
              }).length}
            </p>
            <p className="text-xs text-muted-foreground mt-1">stories in the last 24 h</p>
          </div>
        </div>

        {/* New story form */}
        {showNewForm && (
          <NewStoryForm
            onCancel={() => setShowNewForm(false)}
            onCreate={handleNewStoryCreated}
          />
        )}

        {/* Error */}
        {error && (
          <div className="mb-6 px-4 py-3 rounded-lg bg-red-100 border border-red-300 text-red-700 text-sm">
            {error}
          </div>
        )}

        {/* Stories list */}
        <div>
          <div className="flex items-center justify-between mb-6 gap-4">
            <h2 className="text-3xl flex-shrink-0">Recent Stories</h2>
            {stories.length > 0 && (
              <div className="relative w-64">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground pointer-events-none" />
                <input
                  type="text"
                  placeholder="Search stories…"
                  value={searchQuery}
                  onChange={e => setSearchQuery(e.target.value)}
                  className="w-full pl-9 pr-4 py-2 rounded-lg border border-border bg-background focus:outline-none focus:ring-2 focus:ring-ring text-sm"
                />
              </div>
            )}
          </div>

          {isLoading ? (
            <div className="flex items-center justify-center py-24 text-muted-foreground gap-3">
              <Loader2 className="w-5 h-5 animate-spin" />
              <span>Loading stories…</span>
            </div>
          ) : stories.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-24 text-center">
              <BookOpen className="w-12 h-12 text-muted-foreground mb-4" />
              <h3 className="mb-2">No stories yet</h3>
              <p className="text-sm text-muted-foreground mb-6">
                Start a conversation or create a new story to begin.
              </p>
              <button
                onClick={() => setShowNewForm(true)}
                className="flex items-center gap-2 px-5 py-2.5 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:opacity-90 transition-opacity"
              >
                <Plus className="w-4 h-4" />
                Create your first story
              </button>
            </div>
          ) : filteredStories.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-16 text-muted-foreground text-sm">
              No stories match "{searchQuery}"
            </div>
          ) : (
            <div className="space-y-4">
              {filteredStories.map(story => (
                <div
                  key={story.id}
                  onClick={() => onNavigateStory(story)}
                  className="w-full bg-card border border-border rounded-xl p-6 hover:border-primary transition-colors text-left group cursor-pointer"
                >
                  <div className="flex items-start justify-between mb-3">
                    <h3 className="text-xl group-hover:text-primary transition-colors">{story.title}</h3>
                    <div className="flex items-center gap-2 flex-shrink-0 ml-4">
                      <span className="text-sm text-muted-foreground">
                        {new Date(story.created_at).toLocaleDateString(undefined, {
                          month: 'short', day: 'numeric', year: 'numeric',
                        })}
                      </span>
                      <button
                        onClick={(e) => handleDelete(e, story.id)}
                        className="p-1.5 rounded-lg text-muted-foreground hover:text-red-600 hover:bg-red-50 transition-colors"
                        title="Delete story"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                  <div className="flex items-center gap-3 text-sm text-muted-foreground">
                    <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium ${
                      story.primary_branch_id
                        ? 'bg-green-100 text-green-700'
                        : 'bg-secondary text-muted-foreground'
                    }`}>
                      {story.primary_branch_id ? 'Active' : 'No branches'}
                    </span>
                    <span className="text-xs">Click to view analysis →</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
