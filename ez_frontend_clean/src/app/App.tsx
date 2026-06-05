import { useState } from 'react';
import { ChatPage } from './components/ChatPage';
import { ProfilePage } from './components/ProfilePage';
import { StoryPage } from './components/StoryPage';

type Page = 'chat' | 'profile' | 'story';

export default function App() {
  const [currentPage, setCurrentPage] = useState<Page>('chat');

  return (
    <div className="size-full">
      {currentPage === 'chat' && (
        <ChatPage onNavigateProfile={() => setCurrentPage('profile')} />
      )}
      {currentPage === 'profile' && (
        <ProfilePage
          onNavigateBack={() => setCurrentPage('chat')}
          onNavigateStory={() => setCurrentPage('story')}
        />
      )}
      {currentPage === 'story' && (
        <StoryPage onNavigateBack={() => setCurrentPage('profile')} />
      )}
    </div>
  );
}