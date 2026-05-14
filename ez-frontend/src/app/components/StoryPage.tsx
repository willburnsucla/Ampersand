import { ArrowLeft, Sparkles, TrendingUp, Users, MapPin, Clock } from 'lucide-react';
import { LineChart, Line, BarChart, Bar, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';

const paceData = [
  { chapter: 'Ch 1', tension: 65, engagement: 70 },
  { chapter: 'Ch 2', tension: 72, engagement: 75 },
  { chapter: 'Ch 3', tension: 85, engagement: 88 },
  { chapter: 'Ch 4', tension: 78, engagement: 80 },
  { chapter: 'Ch 5', tension: 90, engagement: 92 },
];

const characterData = [
  { subject: 'Depth', value: 85 },
  { subject: 'Motivation', value: 78 },
  { subject: 'Arc', value: 82 },
  { subject: 'Voice', value: 90 },
  { subject: 'Relatability', value: 75 },
];

const themeData = [
  { theme: 'Identity', strength: 88 },
  { theme: 'Redemption', strength: 72 },
  { theme: 'Sacrifice', strength: 65 },
  { theme: 'Hope', strength: 80 },
];

export function StoryPage({ onNavigateBack }: { onNavigateBack: () => void }) {
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
          <div className="flex items-center gap-3">
            <Sparkles className="w-8 h-8 text-primary" />
            <h1 className="text-4xl">The Midnight Garden</h1>
          </div>
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-6 py-8">
        {/* Story Overview */}
        <div className="bg-gradient-to-br from-primary/10 to-accent/10 border border-border rounded-2xl p-8 mb-8">
          <h2 className="text-3xl mb-4">Story Overview</h2>
          <p className="text-lg leading-relaxed text-foreground/90 mb-6">
            A mysterious garden appears only at midnight, revealing secrets of the past. The protagonist, Elena, discovers she can communicate with spirits who tend the garden, each holding a piece of a century-old mystery that connects to her own family history.
          </p>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className="flex items-center gap-3">
              <MapPin className="w-5 h-5 text-primary" />
              <div>
                <p className="text-sm text-muted-foreground">Setting</p>
                <p>Victorian Estate</p>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <Users className="w-5 h-5 text-primary" />
              <div>
                <p className="text-sm text-muted-foreground">Characters</p>
                <p>7 Main</p>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <Clock className="w-5 h-5 text-primary" />
              <div>
                <p className="text-sm text-muted-foreground">Timeline</p>
                <p>2 Weeks</p>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <TrendingUp className="w-5 h-5 text-primary" />
              <div>
                <p className="text-sm text-muted-foreground">Genre</p>
                <p>Gothic Mystery</p>
              </div>
            </div>
          </div>
        </div>

        {/* AI Insights */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 mb-8">
          {/* Narrative Pace */}
          <div className="bg-card border border-border rounded-xl p-6">
            <h3 className="text-2xl mb-4">Narrative Pace & Engagement</h3>
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={paceData}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                <XAxis dataKey="chapter" stroke="var(--muted-foreground)" />
                <YAxis stroke="var(--muted-foreground)" />
                <Tooltip
                  contentStyle={{
                    backgroundColor: 'var(--card)',
                    border: '1px solid var(--border)',
                    borderRadius: '0.5rem'
                  }}
                />
                <Legend />
                <Line type="monotone" dataKey="tension" stroke="var(--chart-1)" strokeWidth={2} />
                <Line type="monotone" dataKey="engagement" stroke="var(--chart-2)" strokeWidth={2} />
              </LineChart>
            </ResponsiveContainer>
            <p className="text-sm text-muted-foreground mt-4">
              Your story maintains strong tension throughout, with a notable peak in Chapter 5. Consider sustaining this momentum into the climax.
            </p>
          </div>

          {/* Character Analysis */}
          <div className="bg-card border border-border rounded-xl p-6">
            <h3 className="text-2xl mb-4">Character Depth Analysis</h3>
            <ResponsiveContainer width="100%" height={300}>
              <RadarChart data={characterData}>
                <PolarGrid stroke="var(--border)" />
                <PolarAngleAxis dataKey="subject" stroke="var(--muted-foreground)" />
                <PolarRadiusAxis stroke="var(--muted-foreground)" />
                <Radar name="Elena" dataKey="value" stroke="var(--chart-1)" fill="var(--chart-1)" fillOpacity={0.3} />
              </RadarChart>
            </ResponsiveContainer>
            <p className="text-sm text-muted-foreground mt-4">
              Elena shows exceptional voice and depth. Consider strengthening her relatability through more everyday moments between supernatural encounters.
            </p>
          </div>
        </div>

        {/* Theme Strength */}
        <div className="bg-card border border-border rounded-xl p-6 mb-8">
          <h3 className="text-2xl mb-4">Thematic Strength</h3>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={themeData}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis dataKey="theme" stroke="var(--muted-foreground)" />
              <YAxis stroke="var(--muted-foreground)" />
              <Tooltip
                contentStyle={{
                  backgroundColor: 'var(--card)',
                  border: '1px solid var(--border)',
                  borderRadius: '0.5rem'
                }}
              />
              <Bar dataKey="strength" fill="var(--chart-1)" radius={[8, 8, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
          <p className="text-sm text-muted-foreground mt-4">
            Identity emerges as your strongest theme. The interplay between past and present selves creates compelling narrative tension. Sacrifice could be woven in more explicitly.
          </p>
        </div>

        {/* AI Updates Feed */}
        <div className="bg-card border border-border rounded-xl p-6">
          <h3 className="text-2xl mb-6">AI Insights & Suggestions</h3>
          <div className="space-y-6">
            <div className="border-l-4 border-primary pl-4">
              <p className="text-sm text-muted-foreground mb-1">2 hours ago</p>
              <h4 className="mb-2">Plot Structure Suggestion</h4>
              <p className="text-muted-foreground">
                Consider introducing the antagonist's motivation earlier. Currently, their reveal comes late in Chapter 4. Foreshadowing in Chapter 2 could build intrigue.
              </p>
            </div>
            <div className="border-l-4 border-accent pl-4">
              <p className="text-sm text-muted-foreground mb-1">5 hours ago</p>
              <h4 className="mb-2">Worldbuilding Note</h4>
              <p className="text-muted-foreground">
                The garden's magical system is well-defined. You might want to establish clearer rules about what spirits can and cannot do to maintain tension.
              </p>
            </div>
            <div className="border-l-4 border-chart-2 pl-4">
              <p className="text-sm text-muted-foreground mb-1">Yesterday</p>
              <h4 className="mb-2">Dialogue Strength</h4>
              <p className="text-muted-foreground">
                Your dialogue between Elena and Marcus in Chapter 3 feels authentic and reveals character naturally. This approach could be applied to other character interactions.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

/**
 * TODO (once backend has endpoints:)
 * 4–25
paceData, characterData, themeData
GET /stories/:id/analytics (or separate endpoints per chart)
42
Title “The Midnight Garden” hardcoded
GET /stories/:id → title
51–53
Long overview paragraph
GET /stories/:id → summary / synopsis
55–81
Meta: Setting, Characters count, Timeline, Genre
Story metadata fields from API
92–106, 117–122, 134–146
Charts bound to the arrays above
Same analytics payload
108–110, 124–126, 148–150
Paragraphs under charts
AI narrative from API
156–178
“AI Insights & Suggestions” feed — three static blocks with timestamps
GET /stories/:id/insights or activity stream
 */