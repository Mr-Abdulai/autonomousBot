import React, { useState } from 'react';
import Sidebar from './components/Sidebar';
import Cockpit from './pages/Cockpit';
import Cortex from './pages/Cortex';
import DeepMarket from './pages/DeepMarket';
import Ledger from './pages/Ledger';
import DarwinSwarm from './pages/DarwinSwarm';

function App() {
  const [activePage, setActivePage] = useState('cockpit');
  const [mobileOpen, setMobileOpen] = useState(false);

  const renderPage = () => {
    switch (activePage) {
      case 'cockpit': return <Cockpit />;
      case 'cortex': return <Cortex />;
      case 'market': return <DeepMarket />;
      case 'ledger': return <Ledger />;
      case 'darwin': return <DarwinSwarm />;
      default: return <Cockpit />;
    }
  };

  return (
    <div className="flex min-h-screen bg-fintech-bg text-white font-sans">
      <Sidebar
        activePage={activePage}
        setActivePage={setActivePage}
        mobileOpen={mobileOpen}
        setMobileOpen={setMobileOpen}
      />
      <main className="flex-1 lg:ml-64 relative min-w-0">
        {/* Top Gradient Fade */}
        <div className="absolute top-0 left-0 right-0 h-32 bg-gradient-to-b from-blue-900/10 to-transparent pointer-events-none" />

        {renderPage()}
      </main>
    </div>
  );
}

export default App;
