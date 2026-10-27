import React, { useEffect, useState } from 'react';
import {
  ShieldAlert,
  Layers,
  Clock,
  TrendingUp,
  AlertCircle,
  Building2,
  ExternalLink,
} from 'lucide-react';
import { DashboardSummary, SourceInfo } from '../types';
import { PageHead } from '../components/PageHead';
import { api } from '../services/api';

interface OverviewPageProps {
  onSelectStation?: (station: string) => void;
  onNavigateToSources?: (sourceName: string) => void;
  onNavigateToIncidents?: () => void;
}

export const OverviewPage: React.FC<OverviewPageProps> = ({
  onSelectStation,
  onNavigateToSources,
  onNavigateToIncidents,
}) => {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [sources, setSources] = useState<SourceInfo[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;
    setLoading(true);

    Promise.all([api.getDashboardSummary(), api.getSources()])
      .then(([summaryData, sourcesData]) => {
        if (isMounted) {
          setSummary(summaryData);
          setSources(sourcesData.sources);
        }
      })
      .catch((err) => {
        if (isMounted) setError(err.message || 'Failed to fetch dashboard data');
      })
      .finally(() => {
        if (isMounted) setLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, []);

  if (loading) {
    return (
      <div style={{ padding: '4rem', textAlign: 'center', color: 'var(--text-secondary)' }}>
        <p style={{ fontSize: '1.1rem', fontWeight: 500 }}>Connecting to intelligence data layer...</p>
      </div>
    );
  }

  if (error || !summary) {
    return (
      <div className="banner warning" style={{ margin: '2rem 0' }}>
        <div className="banner-content">
          <AlertCircle size={20} />
          <span>Error loading dashboard metrics: {error}</span>
        </div>
      </div>
    );
  }

  // Calculate auxiliary metrics
  const totalEvidenceRecords = summary.by_source
    .filter((s) => s.source !== 'police_incidents')
    .reduce((acc, curr) => acc + curr.count, 0);

  const activeInvestigations =
    summary.by_status.find((s) => s.status === 'UNDER_INVESTIGATION')?.count || 0;
  const openCases =
    summary.by_status.find((s) => s.status === 'OPEN')?.count || 0;

  const maxTimelineCount = Math.max(...summary.incident_timeline.map((t) => t.count), 1);

  return (
    <div>
      <PageHead cmd="xsci overview --all-stations" meta={`${summary.total_incidents.toLocaleString()} incidents · ${sources.length} sources`} />

      {/* Top 4 Stat Cards */}
      <div className="stats-grid">
        <div className="stat-card" onClick={onNavigateToIncidents} style={{ cursor: 'pointer' }}>
          <div className="stat-header">
            <span className="stat-title">Total Incidents</span>
            <div className="stat-icon">
              <ShieldAlert size={18} />
            </div>
          </div>
          <div className="stat-value">{summary.total_incidents.toLocaleString()}</div>
          <div className="stat-sub">
            <span>Across 3 operational jurisdictions</span>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-header">
            <span className="stat-title">Cross-Source Evidence</span>
            <div className="stat-icon" style={{ color: 'var(--accent-emerald)', background: 'rgba(16, 185, 129, 0.15)' }}>
              <Layers size={18} />
            </div>
          </div>
          <div className="stat-value">{totalEvidenceRecords.toLocaleString()}</div>
          <div className="stat-sub">
            <span>Newspaper, CCTV, Witness, Forensics</span>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-header">
            <span className="stat-title">Active Investigations</span>
            <div className="stat-icon" style={{ color: 'var(--accent-amber)', background: 'rgba(245, 158, 11, 0.15)' }}>
              <Clock size={18} />
            </div>
          </div>
          <div className="stat-value">{(activeInvestigations + openCases).toLocaleString()}</div>
          <div className="stat-sub">
            <span>{openCases} Open • {activeInvestigations} Under Active Investigation</span>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-header">
            <span className="stat-title">Tri-Station Balance</span>
            <div className="stat-icon" style={{ color: 'var(--accent-cyan)', background: 'rgba(6, 182, 212, 0.15)' }}>
              <Building2 size={18} />
            </div>
          </div>
          <div className="stat-value">3 Stations</div>
          <div className="stat-sub">
            <span>North, Central, Riverside (~1,000 each)</span>
          </div>
        </div>
      </div>

      {/* Grid: Stations Breakdown & Activity Timeline */}
      <div className="dashboard-grid-2">
        {/* Panel 1: Station Distribution */}
        <div className="panel">
          <div className="panel-title">
            <span>Jurisdictional Distribution</span>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Filter by station</span>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem', marginTop: '0.5rem' }}>
            {summary.by_station.map((st) => {
              const pct = ((st.count / summary.total_incidents) * 100).toFixed(1);
              const color =
                st.station_id === 'NORTH'
                  ? 'var(--accent-amber)'
                  : st.station_id === 'CENTRAL'
                    ? 'var(--accent-blue)'
                    : 'var(--accent-emerald)';

              return (
                <div
                  key={st.station_id}
                  className="dist-item"
                  style={{ cursor: 'pointer' }}
                  onClick={() => onSelectStation?.(st.station_id)}
                >
                  <div className="dist-meta">
                    <span style={{ fontWeight: 600, display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                      <span
                        style={{
                          width: '10px',
                          height: '10px',
                          borderRadius: '50%',
                          background: color,
                        }}
                      />
                      {st.station_id} POLICE STATION
                    </span>
                    <span className="mono-cell">
                      <strong>{st.count.toLocaleString()}</strong> ({pct}%)
                    </span>
                  </div>
                  <div className="dist-bar-bg">
                    <div
                      className="dist-bar-fill"
                      style={{ width: `${pct}%`, background: color }}
                    />
                  </div>
                </div>
              );
            })}
          </div>

          <div style={{ marginTop: '1.5rem', paddingTop: '1rem', borderTop: '1px solid var(--border-subtle)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>
              Click any station to filter exploration table
            </span>
            <button className="page-btn" onClick={onNavigateToIncidents}>
              View All Incidents
            </button>
          </div>
        </div>

        {/* Panel 2: Incident Activity Timeline */}
        <div className="panel">
          <div className="panel-title">
            <span style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <TrendingUp size={16} color="var(--accent-blue)" />
              Incident Activity Over Time
            </span>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Monthly distribution</span>
          </div>

          <div className="timeline-chart">
            {summary.incident_timeline.map((bucket, idx) => {
              const heightPct = (bucket.count / maxTimelineCount) * 100;
              const shortLabel = bucket.period.slice(2); // e.g. "25-01"
              return (
                <div key={idx} className="timeline-bar-col" title={`${bucket.period}: ${bucket.count} incidents`}>
                  <div
                    className="timeline-bar"
                    style={{ height: `${heightPct}%` }}
                  />
                  <span className="timeline-label">{shortLabel}</span>
                </div>
              );
            })}
          </div>

          <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '0.75rem', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
            <span>Start: {summary.incident_timeline[0]?.period || '2025'}</span>
            <span>Monthly Incident Frequency (Peak: {maxTimelineCount})</span>
            <span>End: {summary.incident_timeline[summary.incident_timeline.length - 1]?.period || '2026'}</span>
          </div>
        </div>
      </div>

      {/* Grid: Crime Types & Case Statuses */}
      <div className="dashboard-grid-2">
        {/* Crime Types */}
        <div className="panel">
          <div className="panel-title">
            <span>Crime Type Classification</span>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>10 standard categories</span>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
            {summary.by_crime_type.map((ct) => (
              <div
                key={ct.crime_type}
                style={{
                  background: 'var(--bg-darker)',
                  border: '1px solid var(--border-subtle)',
                  borderRadius: 'var(--radius-sm)',
                  padding: '0.65rem 0.85rem',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                }}
              >
                <span style={{ fontSize: '0.78rem', color: 'var(--text-secondary)' }}>
                  {ct.crime_type.replace('_', ' ')}
                </span>
                <span className="mono-cell" style={{ fontWeight: 600, color: '#fff' }}>
                  {ct.count}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Status Distribution */}
        <div className="panel">
          <div className="panel-title">
            <span>Case Disposition & Status</span>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Investigation lifecycle</span>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.85rem' }}>
            {summary.by_status.map((st) => {
              const pct = ((st.count / summary.total_incidents) * 100).toFixed(1);
              let color = 'var(--accent-blue)';
              if (st.status === 'CLOSED') color = 'var(--accent-emerald)';
              if (st.status === 'UNDER_INVESTIGATION') color = 'var(--accent-amber)';
              if (st.status === 'UNRESOLVED') color = 'var(--accent-rose)';

              return (
                <div key={st.status} className="dist-item">
                  <div className="dist-meta">
                    <span style={{ fontWeight: 500, fontSize: '0.82rem' }}>
                      {st.status.replace('_', ' ')}
                    </span>
                    <span className="mono-cell">
                      {st.count} ({pct}%)
                    </span>
                  </div>
                  <div className="dist-bar-bg">
                    <div
                      className="dist-bar-fill"
                      style={{ width: `${pct}%`, background: color }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* 5 Registered Sources Summary Cards */}
      <div style={{ marginTop: '2rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1.25rem' }}>
          <div>
            <h2 style={{ fontSize: '1.15rem', fontWeight: 700 }}>Registered Intelligence Data Sources</h2>
            <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
              All five source tables registered with NDP File Store schemas
            </p>
          </div>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: '1.25rem' }}>
          {sources.map((src) => (
            <div
              key={src.name}
              className="stat-card"
              style={{ cursor: 'pointer' }}
              onClick={() => onNavigateToSources?.(src.name)}
            >
              <div className="stat-header">
                <span className="stat-title">{src.label}</span>
                <ExternalLink size={14} color="var(--text-muted)" />
              </div>
              <div className="stat-value" style={{ fontSize: '1.6rem' }}>
                {src.record_count.toLocaleString()}
              </div>
              <div style={{ marginTop: '0.5rem', fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                PK: <code className="mono-cell">{src.primary_key_field}</code>
              </div>
              <p style={{ marginTop: '0.5rem', fontSize: '0.74rem', color: 'var(--text-muted)', lineHeight: 1.4 }}>
                {src.description}
              </p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
