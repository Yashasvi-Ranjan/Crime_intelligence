import React, { useEffect, useState } from 'react';
import { Navbar } from './components/Navbar';
import { OverviewPage } from './pages/OverviewPage';
import { IncidentsPage } from './pages/IncidentsPage';
import { SourcesPage } from './pages/SourcesPage';
import { ZetarisStatusPage } from './pages/ZetarisStatusPage';
import { DataSource, ZetarisHealthResponse } from './types';
import { api } from './services/api';

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'overview' | 'incidents' | 'sources' | 'zetaris'>('overview');
  const [stationFilter, setStationFilter] = useState<string>('ALL');
  const [selectedSource, setSelectedSource] = useState<DataSource>('cctv_reports');
  const [zetarisHealth, setZetarisHealth] = useState<ZetarisHealthResponse | null>(null);

  useEffect(() => {
    api
      .getZetarisHealth()
      .then(setZetarisHealth)
      .catch((err) => console.error('Failed to probe Zetaris health:', err));

    // Listen to hash changes for deep linking
    const handleHashChange = () => {
      const hash = window.location.hash.replace('#', '');
      if (['overview', 'incidents', 'sources', 'zetaris'].includes(hash)) {
        setActiveTab(hash as any);
      }
    };

    window.addEventListener('hashchange', handleHashChange);
    if (window.location.hash) handleHashChange();

    return () => window.removeEventListener('hashchange', handleHashChange);
  }, []);

  const handleSelectStation = (station: string) => {
    setStationFilter(station);
    setActiveTab('incidents');
    window.location.hash = '#incidents';
  };

  const handleNavigateToSources = (sourceName: string) => {
    setSelectedSource(sourceName as DataSource);
    setActiveTab('sources');
    window.location.hash = '#sources';
  };

  const handleNavigateToIncidents = () => {
    setStationFilter('ALL');
    setActiveTab('incidents');
    window.location.hash = '#incidents';
  };

  const handleTabChange = (tab: 'overview' | 'incidents' | 'sources' | 'zetaris') => {
    setActiveTab(tab);
    window.location.hash = `#${tab}`;
  };

  return (
    <div className="app-container">
      <Navbar
        activeTab={activeTab}
        setActiveTab={handleTabChange}
        zetarisHealth={zetarisHealth}
      />

      <main className="main-content">
        {activeTab === 'overview' && (
          <OverviewPage
            onSelectStation={handleSelectStation}
            onNavigateToSources={handleNavigateToSources}
            onNavigateToIncidents={handleNavigateToIncidents}
          />
        )}

        {activeTab === 'incidents' && (
          <IncidentsPage initialStation={stationFilter} />
        )}

        {activeTab === 'sources' && (
          <SourcesPage initialSource={selectedSource} />
        )}

        {activeTab === 'zetaris' && <ZetarisStatusPage />}
      </main>
    </div>
  );
};

export default App;
