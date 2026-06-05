import { useState } from 'react';
import { ChatPage } from './components/ChatPage';
import { ProfilePage } from './components/ProfilePage';
import { StoryPage } from './components/StoryPage';
import { SignInPage } from './components/SignInPage';
import { useAuth } from '../lib/auth';
import type { Project } from '../lib/types';

type Page = 'chat' | 'profile' | 'story';

export default function App() {
  const { user, loading } = useAuth();
  const [currentPage, setCurrentPage] = useState<Page>('chat');
  const [selectedProject, setSelectedProject] = useState<Project | null>(null);
  // Increment to force ChatPage to remount with a fresh session
  const [chatKey, setChatKey] = useState(0);

  const handleNavigateStory = (project: Project) => {
    setSelectedProject(project);
    setCurrentPage('story');
  };

  const handleStartNewStory = (project: Project) => {
    setSelectedProject(project);
    setChatKey(k => k + 1);
    setCurrentPage('chat');
  };

  // Re-enter an existing story in the editor (not the read-only analysis view).
  const handleOpenStory = (project: Project) => {
    setSelectedProject(project);
    setChatKey(k => k + 1);
    setCurrentPage('chat');
  };

  if (loading) return null

  if (!user) return <SignInPage />

  return (
    <div className="size-full">
      {currentPage === 'chat' && (
        <ChatPage
          key={chatKey}
          projectId={selectedProject?.id}
          onNavigateProfile={() => setCurrentPage('profile')}
        />
      )}
      {currentPage === 'profile' && (
        <ProfilePage
          onNavigateBack={() => setCurrentPage('chat')}
          onNavigateStory={handleNavigateStory}
          onOpenStory={handleOpenStory}
          onStartNewStory={handleStartNewStory}
        />
      )}
      {currentPage === 'story' && selectedProject && (
        <StoryPage
          onNavigateBack={() => setCurrentPage('profile')}
          projectId={selectedProject.id}
          projectTitle={selectedProject.title}
        />
      )}
    </div>
  );
}
