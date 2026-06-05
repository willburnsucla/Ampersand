import { useEffect, useState } from 'react';
import { ArrowLeft, Sparkles, Users, Hash, AlertCircle, CheckCircle2, Loader2, BookOpen } from 'lucide-react';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ReferenceLine, ResponsiveContainer,
} from 'recharts';
import { listBeats, listBranches, listCharacters, listThemes, listIssues } from '../../lib/api-client';
import type { Beat, Branch, Character, Issue, Theme } from '../../lib/types';

interface StoryPageProps {
  onNavigateBack: () => void;
  projectId: string;
  projectTitle: string;
}

const TURNING_POINT_LABELS: Record<string, string> = {
  tp1: "Inciting Incident",
  tp2: "Rising Action",
  tp3: "Midpoint",
  tp4: "Dark Night",
  tp5: "Climax",
};

const ISSUE_TYPE_COLORS: Record<string, string> = {
  pacing:           "border-amber-400",
  consistency:      "border-red-400",
  character:        "border-blue-400",
  plot:             "border-purple-400",
  worldbuilding:    "border-green-400",
};

function EmotionArcChart({ beats }: { beats: Beat[] }) {
  const sorted = [...beats]
    .sort((a, b) => a.sequence_index_in_branch - b.sequence_index_in_branch)
    .filter(b => b.valence !== null || b.arousal !== null);

  if (sorted.length === 0) {
    return (
      <div className="flex items-center justify-center h-48 text-sm text-muted-foreground">
        Emotion data appears once beats are committed.
      </div>
    );
  }

  const data = sorted.map(b => ({
    name: `Beat ${b.sequence_index_in_branch + 1}`,
    tp: b.turning_point ? TURNING_POINT_LABELS[b.turning_point] : null,
    valence: b.valence !== null ? Math.round(b.valence * 100) : null,
    arousal: b.arousal !== null  ? Math.round(b.arousal  * 100) : null,
  }));

  const tpBeats = data.filter(d => d.tp);

  return (
    <ResponsiveContainer width="100%" height={220}>
      <LineChart data={data} margin={{ top: 8, right: 16, left: 0, bottom: 8 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
        <XAxis dataKey="name" stroke="var(--muted-foreground)" tick={{ fontSize: 10 }} />
        <YAxis domain={[-100, 100]} stroke="var(--muted-foreground)" tick={{ fontSize: 10 }} />
        <Tooltip
          contentStyle={{ backgroundColor: 'var(--card)', border: '1px solid var(--border)', borderRadius: '0.5rem', fontSize: '12px' }}
          formatter={(val: number, key: string) => [`${val > 0 ? '+' : ''}${val}`, key === 'valence' ? 'Valence' : 'Arousal']}
        />
        <ReferenceLine y={0} stroke="var(--border)" strokeDasharray="4 4" />
        {tpBeats.map(d => (
          <ReferenceLine key={d.name} x={d.name} stroke="var(--primary)" strokeOpacity={0.4} strokeDasharray="3 3" label={{ value: d.tp ?? '', position: 'top', fontSize: 8, fill: 'var(--primary)' }} />
        ))}
        <Line type="monotone" dataKey="valence" stroke="var(--chart-1)" strokeWidth={2} dot={{ r: 3 }} connectNulls />
        <Line type="monotone" dataKey="arousal"  stroke="var(--chart-2)" strokeWidth={2} dot={{ r: 3 }} connectNulls strokeDasharray="5 3" />
      </LineChart>
    </ResponsiveContainer>
  );
}

function BeatStatusBar({ beats }: { beats: Beat[] }) {
  const committed = beats.filter(b => b.status === 'committed').length;
  const proposed  = beats.filter(b => b.status === 'proposed').length;
  const rejected  = beats.filter(b => b.status === 'rejected').length;
  const total = beats.length;
  if (total === 0) return null;

  return (
    <div className="flex gap-4 text-sm">
      <span className="flex items-center gap-1.5 text-green-700">
        <CheckCircle2 className="w-4 h-4" />
        {committed} committed
      </span>
      {proposed > 0 && (
        <span className="flex items-center gap-1.5 text-amber-600">
          <Loader2 className="w-4 h-4" />
          {proposed} proposed
        </span>
      )}
      {rejected > 0 && (
        <span className="flex items-center gap-1.5 text-red-500">
          <AlertCircle className="w-4 h-4" />
          {rejected} rejected
        </span>
      )}
    </div>
  );
}

export function StoryPage({ onNavigateBack, projectId, projectTitle }: StoryPageProps) {
  const [beats, setBeats]           = useState<Beat[]>([]);
  const [branches, setBranches]     = useState<Branch[]>([]);
  const [characters, setCharacters] = useState<Character[]>([]);
  const [themes, setThemes]         = useState<Theme[]>([]);
  const [issues, setIssues]         = useState<Issue[]>([]);
  const [isLoading, setIsLoading]   = useState(true);
  const [error, setError]           = useState<string | null>(null);

  useEffect(() => {
    if (!projectId) return;
    setIsLoading(true);
    setError(null);

    listBranches(projectId)
      .then(async (fetchedBranches) => {
        setBranches(fetchedBranches);
        const mainBranch = fetchedBranches[0];

        const [fetchedBeats, fetchedChars, fetchedThemes, fetchedIssues] = await Promise.all([
          mainBranch ? listBeats(projectId, mainBranch.id) : Promise.resolve([]),
          listCharacters(projectId),
          listThemes(projectId),
          mainBranch ? listIssues(projectId, mainBranch.id) : Promise.resolve([]),
        ]);

        setBeats(fetchedBeats);
        setCharacters(fetchedChars);
        setThemes(fetchedThemes);
        setIssues(fetchedIssues);
      })
      .catch(() => setError('Failed to load story data. Is the backend running?'))
      .finally(() => setIsLoading(false));
  }, [projectId]);

  const sortedBeats  = [...beats].sort((a, b) => a.sequence_index_in_branch - b.sequence_index_in_branch);
  const openIssues   = issues.filter(i => i.status === 'open');
  const committedChars   = characters.filter(c => c.status === 'committed');
  const committedThemes  = themes.filter(t => t.status === 'committed');

  return (
    <div className="min-h-screen bg-background pb-12">
      {/* Header */}
      <header className="border-b border-border bg-card px-6 py-4 sticky top-0 z-10">
        <div className="max-w-7xl mx-auto">
          <button
            onClick={onNavigateBack}
            className="flex items-center gap-2 text-muted-foreground hover:text-foreground transition-colors mb-4"
          >
            <ArrowLeft className="w-4 h-4" />
            <span>Back to Profile</span>
          </button>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Sparkles className="w-8 h-8 text-primary" />
              <h1 className="text-4xl">{projectTitle || 'Story'}</h1>
            </div>
            {!isLoading && <BeatStatusBar beats={beats} />}
          </div>
        </div>
      </header>

      {error && (
        <div className="max-w-7xl mx-auto px-6 mt-6">
          <div className="px-4 py-3 rounded-lg bg-red-100 border border-red-300 text-red-700 text-sm">{error}</div>
        </div>
      )}

      {isLoading ? (
        <div className="flex items-center justify-center py-32 text-muted-foreground gap-3">
          <Loader2 className="w-5 h-5 animate-spin" />
          <span>Loading story data…</span>
        </div>
      ) : (
        <div className="max-w-7xl mx-auto px-6 py-8 space-y-8">

          {/* Summary stats */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {[
              { label: 'Beats',      value: beats.length },
              { label: 'Characters', value: committedChars.length },
              { label: 'Themes',     value: committedThemes.length },
              { label: 'Branches',   value: branches.length },
            ].map(({ label, value }) => (
              <div key={label} className="bg-card border border-border rounded-xl p-5 text-center">
                <p className="text-3xl font-semibold">{value}</p>
                <p className="text-sm text-muted-foreground mt-1">{label}</p>
              </div>
            ))}
          </div>

          {/* Emotional arc */}
          <div className="bg-card border border-border rounded-xl p-6">
            <h2 className="text-2xl mb-1">Emotional Arc</h2>
            <p className="text-sm text-muted-foreground mb-4">
              Valence (solid) tracks positive/negative tone; arousal (dashed) tracks intensity. Values are −100 to +100.
            </p>
            <EmotionArcChart beats={sortedBeats} />
          </div>

          {/* Beat timeline + Characters/Themes side-by-side */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">

            {/* Beat timeline */}
            <div className="bg-card border border-border rounded-xl p-6">
              <div className="flex items-center gap-2 mb-4">
                <BookOpen className="w-5 h-5 text-primary" />
                <h2 className="text-2xl">Beat Timeline</h2>
              </div>
              {sortedBeats.length === 0 ? (
                <p className="text-sm text-muted-foreground">No beats yet — start a conversation.</p>
              ) : (
                <ol className="space-y-3">
                  {sortedBeats.map((beat, i) => (
                    <li key={beat.id} className="flex gap-3">
                      <div className="flex flex-col items-center flex-shrink-0">
                        <div className={`w-6 h-6 rounded-full border-2 flex items-center justify-center text-[9px] font-bold ${
                          beat.status === 'committed' ? 'border-primary bg-primary/20 text-primary' :
                          beat.status === 'rejected'  ? 'border-muted-foreground bg-muted text-muted-foreground opacity-50' :
                          'border-accent bg-accent/20 text-accent-foreground'
                        }`}>
                          {i + 1}
                        </div>
                        {i < sortedBeats.length - 1 && <div className="w-px flex-1 bg-border my-1 min-h-[10px]" />}
                      </div>
                      <div className={`flex-1 pb-2 ${beat.status === 'rejected' ? 'opacity-50' : ''}`}>
                        {beat.turning_point && (
                          <p className="text-[9px] font-semibold uppercase tracking-wider text-primary/70 mb-0.5">
                            {TURNING_POINT_LABELS[beat.turning_point]}
                          </p>
                        )}
                        <p className={`text-sm leading-relaxed ${beat.status === 'rejected' ? 'line-through' : ''}`}>
                          {beat.logline}
                        </p>
                      </div>
                    </li>
                  ))}
                </ol>
              )}
            </div>

            {/* Characters & Themes */}
            <div className="space-y-6">
              <div className="bg-card border border-border rounded-xl p-6">
                <div className="flex items-center gap-2 mb-4">
                  <Users className="w-5 h-5 text-primary" />
                  <h2 className="text-2xl">Characters</h2>
                </div>
                {committedChars.length === 0 ? (
                  <p className="text-sm text-muted-foreground">Characters emerge as you develop the story.</p>
                ) : (
                  <div className="flex flex-wrap gap-2">
                    {committedChars.map(c => (
                      <span key={c.id} className="px-3 py-1.5 rounded-full bg-primary/10 text-primary text-sm font-medium">
                        {c.name}
                      </span>
                    ))}
                    {characters.filter(c => c.status === 'proposed').map(c => (
                      <span key={c.id} className="px-3 py-1.5 rounded-full bg-amber-100 text-amber-700 text-sm">
                        {c.name} <span className="opacity-60 text-xs">(proposed)</span>
                      </span>
                    ))}
                  </div>
                )}
              </div>

              <div className="bg-card border border-border rounded-xl p-6">
                <div className="flex items-center gap-2 mb-4">
                  <Hash className="w-5 h-5 text-primary" />
                  <h2 className="text-2xl">Themes</h2>
                </div>
                {committedThemes.length === 0 ? (
                  <p className="text-sm text-muted-foreground">Themes are extracted as the story develops.</p>
                ) : (
                  <div className="flex flex-wrap gap-2">
                    {committedThemes.map(t => (
                      <span key={t.id} className="px-3 py-1.5 rounded-full bg-secondary text-foreground text-sm border border-border">
                        {t.name}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* AI Insights (real issues from backend) */}
          <div className="bg-card border border-border rounded-xl p-6">
            <div className="flex items-center gap-2 mb-6">
              <Sparkles className="w-5 h-5 text-primary" />
              <h2 className="text-2xl">AI Insights</h2>
              {openIssues.length > 0 && (
                <span className="ml-auto text-xs bg-amber-100 text-amber-700 px-2 py-0.5 rounded-full border border-amber-200">
                  {openIssues.length} open
                </span>
              )}
            </div>

            {issues.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                No issues detected yet. Keep writing — insights appear as your story develops.
              </p>
            ) : (
              <div className="space-y-5">
                {openIssues.map(issue => (
                  <div
                    key={issue.id}
                    className={`border-l-4 pl-4 ${ISSUE_TYPE_COLORS[issue.type] ?? 'border-primary'}`}
                  >
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                        {issue.type.replace(/_/g, ' ')}
                      </span>
                      <span className="text-xs text-muted-foreground">
                        · {new Date(issue.detected_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}
                      </span>
                    </div>
                    <p className="text-sm text-foreground leading-relaxed">{issue.description}</p>
                  </div>
                ))}
                {issues.filter(i => i.status !== 'open').map(issue => (
                  <div key={issue.id} className="border-l-4 border-border pl-4 opacity-50">
                    <div className="flex items-center gap-2 mb-1">
                      <CheckCircle2 className="w-3 h-3 text-green-500" />
                      <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                        {issue.type.replace(/_/g, ' ')} · resolved
                      </span>
                    </div>
                    <p className="text-sm text-muted-foreground leading-relaxed">{issue.description}</p>
                  </div>
                ))}
              </div>
            )}
          </div>

        </div>
      )}
    </div>
  );
}
