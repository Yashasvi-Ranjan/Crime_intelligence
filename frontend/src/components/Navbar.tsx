import React from 'react';
import { ZetarisHealthResponse } from '../types';
import { Tab, TABS } from '../lib/tabs';

interface NavbarProps {
  activeTab: Tab;
  setActiveTab: (tab: Tab) => void;
  zetarisHealth: ZetarisHealthResponse | null;
  onOpenPalette: () => void;
}

export const Navbar: React.FC<NavbarProps> = ({ activeTab, setActiveTab, zetarisHealth, onOpenPalette }) => {
  const isZetarisLive = zetarisHealth?.status === 'connected';

  return (
    <header className="top-nav">
      <div className="brand-section">
        <span className="brand-logo">▌XSCI</span>
        <div className="brand-title-group">
          <h1>CROSS-STATION INTEL</h1>
          <span className="brand-subtitle">north · central · riverside</span>
        </div>
      </div>

      <nav className="nav-links" aria-label="Primary">
        {TABS.map((t, i) => (
          <button
            key={t.id}
            className={`nav-btn ${activeTab === t.id ? 'active' : ''}`}
            onClick={() => setActiveTab(t.id)}
            aria-current={activeTab === t.id ? 'page' : undefined}
          >
            <kbd>{i + 1}</kbd>
            {t.label}
          </button>
        ))}
      </nav>

      <div className="header-status">
        <button className="cmdk-hint" onClick={onOpenPalette} aria-label="Open command palette">
          <span>search / jump</span>
          <kbd style={{ border: '1px solid var(--border-strong)', padding: '0 4px' }}>⌘K</kbd>
        </button>
        <div
          className={`status-pill ${isZetarisLive ? 'connected' : 'not_configured'}`}
          title={zetarisHealth?.message || 'Checking data layer status...'}
        >
          <div className="status-dot" />
          <span>{isZetarisLive ? 'ZETARIS LIVE' : 'LOCAL FALLBACK'}</span>
        </div>
      </div>
    </header>
  );
};
