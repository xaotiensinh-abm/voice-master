import { useState } from 'react';
import Sidebar from './components/Sidebar';
import CreateVoice from './components/CreateVoice';
import VoiceLibrary from './components/VoiceLibrary';
import History from './components/History';
import Settings from './components/Settings';
import Diagnostics from './components/Diagnostics';
import AgentConnect from './components/AgentConnect';
import License from './components/License';
import { useHealth } from './hooks/useHealth';

type Screen = 'create' | 'library' | 'history' | 'settings' | 'diagnostics' | 'agent' | 'license';

export default function App() {
  const [activeScreen, setActiveScreen] = useState<Screen>('create');
  const health = useHealth();

  const renderScreen = () => {
    switch (activeScreen) {
      case 'create':
        return <CreateVoice health={health} />;
      case 'library':
        return <VoiceLibrary />;
      case 'history':
        return <History />;
      case 'settings':
        return <Settings />;
      case 'diagnostics':
        return <Diagnostics health={health} />;
      case 'agent':
        return <AgentConnect health={health} />;
      case 'license':
        return <License />;
      default:
        return <CreateVoice health={health} />;
    }
  };

  return (
    <div className="app-layout">
      <Sidebar
        activeScreen={activeScreen}
        onNavigate={setActiveScreen}
        connected={health.connected}
        version={health.version}
        license={health.data?.license}
      />
      <main className="app-content">
        {renderScreen()}
      </main>
    </div>
  );
}
