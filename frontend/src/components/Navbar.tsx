import React from 'react';
import { Shield, Database, LayoutDashboard, FileSearch, Layers, BrainCircuit } from 'lucide-react';
import { ZetarisHealthResponse } from '../types';

interface NavbarProps {
  activeTab: 'overview' | 'investigation' | 'incidents' | 'sources' | 'zetaris';
  setActiveTab: (tab: 'overview' | 'investigation' | 'incidents' | 'sources' | 'zetaris') => void;
  zetarisHealth: ZetarisHealthResponse | null;
}

export const Navbar: React.FC<NavbarProps> = ({
  activeTab,
  setActiveTab,
  zetarisHealth,
}) => {
  const isZetarisLive = zetarisHealth?.status === 'connected';

  return (
    <header className="top-nav">
      <div className="brand-section">
        <div className="brand-logo">
          <Shield size={22} />
        </div>
        <div className="brand-title-group">
          <h1>CROSS-STATION CRIME INTELLIGENCE</h1>
          <span className="brand-subtitle">
            North • Central • Riverside Operations
          </span>
        </div>
      </div>

      <nav className="nav-links">
        <button
          className={`nav-btn ${activeTab === 'overview' ? 'active' : ''}`}
          onClick={() => setActiveTab('overview')}
        >
          <LayoutDashboard size={15} />
          Overview
        </button>
        <button
          className={`nav-btn ${activeTab === 'investigation' ? 'active' : ''}`}
          onClick={() => setActiveTab('investigation')}
          style={activeTab === 'investigation' ? { borderColor: 'var(--accent-purple)', color: '#fff' } : {}}
        >
          <BrainCircuit size={15} color={activeTab === 'investigation' ? 'var(--accent-purple)' : undefined} />
          Investigation Hub
        </button>
        <button
          className={`nav-btn ${activeTab === 'incidents' ? 'active' : ''}`}
          onClick={() => setActiveTab('incidents')}
        >
          <FileSearch size={15} />
          Incidents
        </button>
        <button
          className={`nav-btn ${activeTab === 'sources' ? 'active' : ''}`}
          onClick={() => setActiveTab('sources')}
        >
          <Layers size={15} />
          Source Explorer
        </button>
        <button
          className={`nav-btn ${activeTab === 'zetaris' ? 'active' : ''}`}
          onClick={() => setActiveTab('zetaris')}
        >
          <Database size={15} />
          Zetaris Layer
        </button>
      </nav>

      <div className="header-status">
        <div
          className={`status-pill ${isZetarisLive ? 'connected' : 'not_configured'}`}
          title={zetarisHealth?.message || 'Checking data layer status...'}
        >
          <div className="status-dot" />
          <span>
            {isZetarisLive ? 'ZETARIS: LIVE' : 'DATA: LOCAL FALLBACK'}
          </span>
        </div>
      </div>
    </header>
  );
};
