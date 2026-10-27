import React, { useEffect, useState } from 'react';
import { Navbar } from './components/Navbar';
import { StatusBar } from './components/StatusBar';
import { CommandPalette, tabCommands } from './components/CommandPalette';
import { Tab, TABS } from './lib/tabs';
import { OfflineBanner } from './components/OfflineBanner';
import { OverviewPage } from './pages/OverviewPage';
import { InvestigationPage } from './pages/InvestigationPage';
import { IncidentsPage } from './pages/IncidentsPage';
import { SourcesPage } from './pages/SourcesPage';
import { ZetarisStatusPage } from './pages/ZetarisStatusPage';
import { DataSource, ZetarisHealthResponse } from './types';
import { api } from './services/api';

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<Tab>('investigation')
  const [paletteOpen, setPaletteOpen] = useState(false);
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
      if (TABS.some((t) => t.id === hash)) {
        setActiveTab(hash as Tab);
      }
    };

    window.addEventListener('hashchange', handleHashChange);
    if (window.location.hash) handleHashChange();

    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement;
      const typing = t?.tagName === 'INPUT' || t?.tagName === 'TEXTAREA' || t?.tagName === 'SELECT' || t?.isContentEditable;
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        setPaletteOpen((o) => !o);
      } else if (!typing && !e.metaKey && !e.ctrlKey && !e.altKey && /^[1-5]$/.test(e.key)) {
        const tab = TABS[Number(e.key) - 1].id;
        setActiveTab(tab);
        window.location.hash = `#${tab}`;
      }
    };
    window.addEventListener('keydown', onKey);

    return () => {
      window.removeEventListener('hashchange', handleHashChange);
      window.removeEventListener('keydown', onKey);
    };
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

  const handleTabChange = (tab: Tab) => {
    setActiveTab(tab);
    window.location.hash = `#${tab}`;
  };

  return (
    <div className="app-container">
      <OfflineBanner />
      <Navbar
        activeTab={activeTab}
        setActiveTab={handleTabChange}
        zetarisHealth={zetarisHealth}
        onOpenPalette={() => setPaletteOpen(true)}
      />

      <main className="main-content">
        {activeTab === 'overview' && (
          <OverviewPage
            onSelectStation={handleSelectStation}
            onNavigateToSources={handleNavigateToSources}
            onNavigateToIncidents={handleNavigateToIncidents}
          />
        )}

        {activeTab === 'investigation' && <InvestigationPage />}

        {activeTab === 'incidents' && (
          <IncidentsPage initialStation={stationFilter} />
        )}

        {activeTab === 'sources' && (
          <SourcesPage initialSource={selectedSource} />
        )}

        {activeTab === 'zetaris' && <ZetarisStatusPage />}
      </main>

      <StatusBar tab={activeTab} zetarisHealth={zetarisHealth} />
      <CommandPalette
        open={paletteOpen}
        onClose={() => setPaletteOpen(false)}
        commands={[
          ...tabCommands(handleTabChange),
          ...['NORTH', 'CENTRAL', 'RIVERSIDE'].map((st) => ({
            id: `st-${st}`,
            label: `xsci incidents --station ${st.toLowerCase()}`,
            hint: 'filter',
            run: () => handleSelectStation(st),
          })),
        ]}
      />
    </div>
  );
};

export default App;
