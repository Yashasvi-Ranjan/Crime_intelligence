import React, { useState, useMemo } from 'react';
import {
  Pin,
  PinOff,
  Camera,
  Microscope,
  Eye,
  FileText,
  Shield,
  Search,
  CheckCircle2,
  Download,
  X,
  Info,
} from 'lucide-react';
import {
  CandidateLink,
  EvidenceCardItem,
} from '../types/investigation';

interface EvidencePinboardProps {
  supportingEvidence?: {
    cctv_reports?: Record<string, any>[];
    witness_reports?: Record<string, any>[];
    forensic_reports?: Record<string, any>[];
    newspaper_reports?: Record<string, any>[];
  };
  candidateIncidents?: Record<string, any>[];
  candidateLinks?: CandidateLink[];
  onOpenDossier?: () => void;
  onSelectIncident?: (incidentId: string) => void;
}

const groundingLabel = (s: EvidenceCardItem['groundingStatus']) =>
  s === 'SUPPORTED' ? 'Cited by a verifier-SUPPORTED link'
  : s === 'WEAK' ? 'Cited by a WEAK link'
  : s === 'UNSUPPORTED' ? 'Cited by an UNSUPPORTED link'
  : s === 'NOT_AVAILABLE' ? 'Verifier status not available'
  : 'Not cited by any link';
const groundingColor = (s: EvidenceCardItem['groundingStatus']) =>
  s === 'SUPPORTED' ? '#10b981' : s === 'WEAK' ? '#f59e0b' : s === 'UNSUPPORTED' ? '#f43f5e' : '#64748b';

export const EvidencePinboard: React.FC<EvidencePinboardProps> = ({
  supportingEvidence,
  candidateIncidents = [],
  candidateLinks: _candidateLinks = [],
  onOpenDossier,
  onSelectIncident: _onSelectIncident,
}) => {
  // Normalize evidence into uniform EvidenceCardItem list
  const allCards: EvidenceCardItem[] = useMemo(() => {
    const list: EvidenceCardItem[] = [];
    // Verifier status per record, derived only from the links that cite it (best status wins).
    const rank: Record<string, number> = { SUPPORTED: 3, WEAK: 2, UNSUPPORTED: 1 };
    const statusById: Record<string, EvidenceCardItem['groundingStatus']> = {};
    for (const l of _candidateLinks) {
      for (const eid of l.supporting_evidence_ids ?? []) {
        const st = (l.validation_status ?? 'NOT_AVAILABLE') as EvidenceCardItem['groundingStatus'];
        const cur = statusById[eid];
        if (!cur || (rank[st] ?? 0) > (rank[cur] ?? 0)) statusById[eid] = st;
      }
    }
    const statusFor = (id: string): EvidenceCardItem['groundingStatus'] => statusById[id] ?? 'NOT_CITED';
    const ev = supportingEvidence || {};

    // 1. CCTV Reports
    (ev.cctv_reports || []).forEach((cctv) => {
      const id = cctv.cctv_report_id || cctv.id || 'CCTV-UNKNOWN';
      const incId = cctv.incident_id || cctv.station_incident_id || '';
      list.push({
        id,
        type: 'cctv',
        title: `Surveillance Camera ${cctv.camera_id || id}`,
        station: cctv.station_id || cctv.precinct || 'n/a',
        timestamp: cctv.timestamp || cctv.recorded_at || undefined,
        location: cctv.camera_location || cctv.location || undefined,
        summary: cctv.observations || cctv.description || '(no description in record)',
        corroboratesIncidentIds: incId ? [incId] : [],
        groundingStatus: statusFor(id),
        citations: [`cctv_reports.${id}`],
        metadata: cctv,
      });
    });

    // 2. Forensic Lab Telemetry
    (ev.forensic_reports || []).forEach((forRep) => {
      const id = forRep.report_id || forRep.id || 'FOR-UNKNOWN';
      const incId = forRep.incident_id || forRep.station_incident_id || '';
      list.push({
        id,
        type: 'forensic',
        title: `Forensic Lab Telemetry: ${forRep.analysis_type || 'record'}`,
        station: forRep.station_id || forRep.precinct || 'n/a',
        timestamp: forRep.analyzed_at || forRep.timestamp || undefined,
        location: forRep.laboratory || undefined,
        summary: forRep.findings || forRep.description || '(no description in record)',
        corroboratesIncidentIds: incId ? [incId] : [],
        groundingStatus: statusFor(id),
        citations: [`forensic_reports.${id}`],
        metadata: forRep,
      });
    });

    // 3. Witness Statements
    (ev.witness_reports || []).forEach((wit) => {
      const id = wit.statement_id || wit.id || 'WIT-UNKNOWN';
      const incId = wit.incident_id || wit.station_incident_id || '';
      list.push({
        id,
        type: 'witness',
        title: `Witness Statement (${wit.witness_type || 'unspecified'})`,
        station: wit.station_id || wit.precinct || 'n/a',
        timestamp: wit.statement_time || wit.timestamp || undefined,
        location: wit.interview_location || undefined,
        summary: wit.statement || wit.description || '(no description in record)',
        corroboratesIncidentIds: incId ? [incId] : [],
        groundingStatus: statusFor(id),
        citations: [`witness_reports.${id}`],
        metadata: wit,
      });
    });

    // 4. Newspaper Clippings
    (ev.newspaper_reports || []).forEach((news) => {
      const id = news.article_id || news.id || 'NEWS-UNKNOWN';
      const incId = news.incident_id || news.station_incident_id || '';
      list.push({
        id,
        type: 'newspaper',
        title: news.headline || news.title || 'News record',
        station: news.station_id || news.precinct || 'n/a',
        timestamp: news.publication_date || news.timestamp || undefined,
        location: news.publisher || undefined,
        summary: news.excerpt || news.description || '(no description in record)',
        corroboratesIncidentIds: incId ? [incId] : [],
        groundingStatus: statusFor(id),
        citations: [`newspaper_reports.${id}`],
        metadata: news,
      });
    });

    // 5. Candidate Incidents as primary case cards
    candidateIncidents.forEach((inc) => {
      const id = inc.incident_id || 'INC-RECORD';
      list.push({
        id,
        type: 'incident',
        title: `Incident: ${inc.crime_type || 'unspecified'}`,
        station: inc.station_id || 'n/a',
        timestamp: inc.occurred_from || inc.reported_at || undefined,
        location: inc.location_description || inc.location_id || undefined,
        summary: inc.method_description || '(no description in record)',
        corroboratesIncidentIds: [id],
        groundingStatus: statusFor(id),
        citations: [`police_incidents.${id}`],
        metadata: inc,
      });
    });

    return list;
  }, [supportingEvidence, candidateIncidents, _candidateLinks]);

  // Initial pinned cards (default pin the top 4 key items)
  const [pinnedIds, setPinnedIds] = useState<Set<string>>(() => {
    const initial = new Set<string>();
    allCards.slice(0, 4).forEach((c) => initial.add(c.id));
    return initial;
  });

  // Filters
  const [categoryFilter, setCategoryFilter] = useState<string>('ALL');
  const [stationFilter, setStationFilter] = useState<string>('ALL');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [selectedCardForModal, setSelectedCardForModal] = useState<EvidenceCardItem | null>(null);

  // Toggle pin
  const togglePin = (id: string, e?: React.MouseEvent) => {
    if (e) e.stopPropagation();
    setPinnedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  // Pin/Unpin all
  const pinAll = () => {
    setPinnedIds(new Set(allCards.map((c) => c.id)));
  };
  const unpinAll = () => {
    setPinnedIds(new Set());
  };

  // Filtered Cards
  const filteredCards = useMemo(() => {
    return allCards.filter((c) => {
      // Category filter
      if (categoryFilter === 'PINNED') {
        if (!pinnedIds.has(c.id)) return false;
      } else if (categoryFilter !== 'ALL' && c.type !== categoryFilter.toLowerCase()) {
        return false;
      }

      // Station filter
      if (stationFilter !== 'ALL' && !c.station.toUpperCase().includes(stationFilter)) {
        return false;
      }

      // Search query
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        const inId = c.id.toLowerCase().includes(q);
        const inTitle = c.title.toLowerCase().includes(q);
        const inSummary = c.summary.toLowerCase().includes(q);
        const inLocation = (c.location || '').toLowerCase().includes(q);
        if (!inId && !inTitle && !inSummary && !inLocation) return false;
      }

      return true;
    });
  }, [allCards, categoryFilter, stationFilter, searchQuery, pinnedIds]);

  const getCategoryConfig = (type: string) => {
    switch (type) {
      case 'cctv':
        return { color: '#06b6d4', fill: 'rgba(6, 182, 212, 0.15)', border: 'rgba(6, 182, 212, 0.3)', icon: Camera, label: 'CCTV Surveillance' };
      case 'forensic':
        return { color: '#10b981', fill: 'rgba(16, 185, 129, 0.15)', border: 'rgba(16, 185, 129, 0.3)', icon: Microscope, label: 'Forensic Lab' };
      case 'witness':
        return { color: '#b99cf5', fill: 'rgba(168, 85, 247, 0.15)', border: 'rgba(168, 85, 247, 0.3)', icon: Eye, label: 'Witness Statement' };
      case 'newspaper':
        return { color: '#f59e0b', fill: 'rgba(245, 158, 11, 0.15)', border: 'rgba(245, 158, 11, 0.3)', icon: FileText, label: 'News Record' };
      default:
        return { color: '#5cc8e6', fill: 'rgba(92, 200, 230, 0.35)', border: 'rgba(92, 200, 230, 0.35)', icon: Shield, label: 'Incident Record' };
    }
  };

  return (
    <div
      style={{
        background: 'var(--bg-card, #0f172a)',
        border: '1px solid var(--border-subtle, var(--border-strong))',
        borderRadius: 'var(--radius-md)',
        padding: '1.25rem',
        boxShadow: '0 8px 30px rgba(0, 0, 0, 0.35)',
        display: 'flex',
        flexDirection: 'column',
        gap: '1.2rem',
      }}
    >
      {/* ── Pinboard Header & Quick Actions ───────────────────────────────────── */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: '1rem',
          borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
          paddingBottom: '1rem',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <div
            style={{
              background: 'var(--accent-green)',
              padding: '8px',
              borderRadius: 'var(--radius-md)',
              color: '#fff',
              display: 'flex',
              alignItems: 'center',
              boxShadow: '0 0 15px rgba(245, 158, 11, 0.35)',
            }}
          >
            <Pin size={20} />
          </div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <h3 style={{ fontSize: '1.05rem', fontWeight: 700, margin: 0, letterSpacing: '0.02em', color: '#f8fafc' }}>
                INTERACTIVE EVIDENCE PINBOARD WORKSPACE
              </h3>
              <span
                style={{
                  fontSize: '0.65rem',
                  fontWeight: 700,
                  padding: '2px 8px',
                  borderRadius: 'var(--radius-md)',
                  background: 'rgba(245, 158, 11, 0.15)',
                  color: '#f59e0b',
                  border: '1px solid rgba(245, 158, 11, 0.3)',
                }}
              >
                {pinnedIds.size} ITEMS PINNED
              </span>
            </div>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary, #94a3b8)' }}>
              Pin, Organize, and Corroborate Cross-Station Intelligence for Review
            </span>
          </div>
        </div>

        {/* Action Buttons */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <button
            onClick={pinAll}
            style={{
              fontSize: '0.7rem',
              fontWeight: 600,
              padding: '4px 10px',
              borderRadius: 'var(--radius-md)',
              background: 'var(--bg-elevated)',
              border: '1px solid var(--border-strong)',
              color: '#94a3b8',
              cursor: 'pointer',
            }}
          >
            Pin All
          </button>
          <button
            onClick={unpinAll}
            style={{
              fontSize: '0.7rem',
              fontWeight: 600,
              padding: '4px 10px',
              borderRadius: 'var(--radius-md)',
              background: 'var(--bg-elevated)',
              border: '1px solid var(--border-strong)',
              color: '#94a3b8',
              cursor: 'pointer',
            }}
          >
            Unpin All
          </button>

          {onOpenDossier && (
            <button
              onClick={onOpenDossier}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                padding: '6px 12px',
                borderRadius: 'var(--radius-md)',
                background: 'var(--accent-green)',
                color: '#fff',
                border: 'none',
                fontSize: '0.75rem',
                fontWeight: 600,
                cursor: 'pointer',
                boxShadow: '0 2px 10px rgba(14, 165, 233, 0.3)',
              }}
            >
              <Download size={13} /> Export Pinned to Dossier
            </button>
          )}
        </div>
      </div>

      {/* ── Toolbar: Search & Category Filter Pills ───────────────────────────── */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: '12px',
          background: 'var(--bg-card)',
          padding: '0.75rem 1rem',
          borderRadius: 'var(--radius-md)',
          border: '1px solid rgba(255, 255, 255, 0.05)',
        }}
      >
        {/* Search */}
        <div style={{ position: 'relative', minWidth: '200px', flex: '1 1 200px' }}>
          <Search size={14} style={{ position: 'absolute', left: '10px', top: '50%', transform: 'translateY(-50%)', color: '#64748b' }} />
          <input
            type="text"
            placeholder="Search evidence cards, statements, camera IDs..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            style={{
              width: '100%',
              padding: '6px 10px 6px 30px',
              borderRadius: 'var(--radius-md)',
              border: '1px solid var(--border-strong)',
              background: 'var(--bg-elevated)',
              color: '#fff',
              fontSize: '0.75rem',
            }}
          />
        </div>

        {/* Categories */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap' }}>
          {[
            { id: 'ALL', label: 'All Cards', count: allCards.length },
            { id: 'PINNED', label: 'Pinned Only', count: pinnedIds.size },
            { id: 'cctv', label: 'CCTV Feeds', count: allCards.filter((c) => c.type === 'cctv').length },
            { id: 'forensic', label: 'Forensic Lab', count: allCards.filter((c) => c.type === 'forensic').length },
            { id: 'witness', label: 'Witness Statements', count: allCards.filter((c) => c.type === 'witness').length },
            { id: 'newspaper', label: 'News Clippings', count: allCards.filter((c) => c.type === 'newspaper').length },
            { id: 'incident', label: 'Incidents', count: allCards.filter((c) => c.type === 'incident').length },
          ].map((cat) => {
            const active = categoryFilter === cat.id;
            return (
              <button
                key={cat.id}
                onClick={() => setCategoryFilter(cat.id)}
                style={{
                  fontSize: '0.65rem',
                  fontWeight: 600,
                  padding: '3px 8px',
                  borderRadius: 'var(--radius-md)',
                  background: active ? 'rgba(92, 200, 230, 0.35)' : 'var(--bg-elevated)',
                  color: active ? '#818cf8' : '#64748b',
                  border: `1px solid ${active ? '#5cc8e6' : 'var(--border-strong)'}`,
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '4px',
                }}
              >
                <span>{cat.label}</span>
                <span style={{ fontSize: '0.6rem', opacity: 0.7 }}>({cat.count})</span>
              </button>
            );
          })}
        </div>

        {/* Precinct Filter */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <span style={{ fontSize: '0.7rem', color: '#94a3b8', fontWeight: 600 }}>PRECINCT:</span>
          {['ALL', 'NORTH', 'CENTRAL', 'RIVERSIDE'].map((st) => (
            <button
              key={st}
              onClick={() => setStationFilter(st)}
              style={{
                fontSize: '0.65rem',
                fontWeight: 600,
                padding: '3px 7px',
                borderRadius: 'var(--radius-sm)',
                background: stationFilter === st ? 'rgba(56, 189, 248, 0.25)' : 'var(--bg-elevated)',
                color: stationFilter === st ? '#38bdf8' : '#64748b',
                border: `1px solid ${stationFilter === st ? '#38bdf8' : 'var(--border-strong)'}`,
                cursor: 'pointer',
              }}
            >
              {st}
            </button>
          ))}
        </div>
      </div>

      {/* ── Corkboard Grid of Evidence Cards ─────────────────────────────────── */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(290px, 1fr))',
          gap: '1rem',
          maxHeight: '620px',
          overflowY: 'auto',
          padding: '4px',
        }}
      >
        {filteredCards.length === 0 && (
          <div
            style={{
              gridColumn: '1 / -1',
              padding: '3rem',
              textAlign: 'center',
              color: '#64748b',
              background: 'var(--bg-card)',
              borderRadius: 'var(--radius-md)',
              border: '1px dashed var(--border-strong)',
            }}
          >
            No evidence cards match the active category, precinct, or search filter.
          </div>
        )}

        {filteredCards.map((card) => {
          const isPinned = pinnedIds.has(card.id);
          const cfg = getCategoryConfig(card.type);
          const IconComp = cfg.icon;

          return (
            <div
              key={card.id}
              onClick={() => setSelectedCardForModal(card)}
              style={{
                background: isPinned
                  ? 'linear-gradient(135deg, var(--bg-elevated) 0%, var(--bg-card) 100%)'
                  : 'var(--bg-card)',
                border: isPinned
                  ? '1.5px solid rgba(245, 158, 11, 0.6)'
                  : '1px solid var(--border-strong)',
                borderRadius: 'var(--radius-md)',
                padding: '1rem',
                display: 'flex',
                flexDirection: 'column',
                gap: '0.6rem',
                position: 'relative',
                cursor: 'pointer',
                transition: 'all 0.2s ease',
                boxShadow: isPinned ? '0 4px 20px rgba(245, 158, 11, 0.15)' : 'none',
              }}
            >
              {/* Pushpin Button in Corner */}
              <button
                onClick={(e) => togglePin(card.id, e)}
                title={isPinned ? 'Unpin card' : 'Pin card to Corkboard'}
                style={{
                  position: 'absolute',
                  top: '10px',
                  right: '10px',
                  background: isPinned ? 'rgba(245, 158, 11, 0.25)' : 'var(--bg-elevated)',
                  border: `1px solid ${isPinned ? '#f59e0b' : 'var(--border-strong)'}`,
                  color: isPinned ? '#fbbf24' : '#64748b',
                  borderRadius: '50%',
                  width: '28px',
                  height: '28px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  cursor: 'pointer',
                  zIndex: 2,
                  transition: 'all 0.15s ease',
                }}
              >
                {isPinned ? <Pin size={14} /> : <PinOff size={14} />}
              </button>

              {/* Card Category Header */}
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', paddingRight: '28px' }}>
                <div
                  style={{
                    background: cfg.fill,
                    color: cfg.color,
                    padding: '4px',
                    borderRadius: 'var(--radius-md)',
                    border: `1px solid ${cfg.border}`,
                    display: 'flex',
                    alignItems: 'center',
                  }}
                >
                  <IconComp size={14} />
                </div>
                <div>
                  <span style={{ fontSize: '0.65rem', fontWeight: 700, color: cfg.color, textTransform: 'uppercase' }}>
                    {cfg.label}
                  </span>
                  <div style={{ fontSize: '0.65rem', color: '#64748b' }}>
                    ID: <strong style={{ color: '#cbd5e1' }}>{card.id}</strong>
                  </div>
                </div>
              </div>

              {/* Card Title */}
              <h4 style={{ fontSize: '0.85rem', fontWeight: 700, color: '#f8fafc', margin: '2px 0 0 0', lineHeight: '1.3' }}>
                {card.title}
              </h4>

              {/* Card Summary */}
              <p
                style={{
                  fontSize: '0.75rem',
                  lineHeight: '1.4',
                  color: '#94a3b8',
                  margin: 0,
                  display: '-webkit-box',
                  WebkitLineClamp: 3,
                  WebkitBoxOrient: 'vertical',
                  overflow: 'hidden',
                }}
              >
                {card.summary}
              </p>

              {/* Corroborated Incidents & Station Badges */}
              <div style={{ marginTop: 'auto', paddingTop: '6px', borderTop: '1px solid rgba(255, 255, 255, 0.06)', display: 'flex', flexDirection: 'column', gap: '4px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.65rem' }}>
                  <span style={{ color: '#64748b' }}>Precinct:</span>
                  <span style={{ color: '#38bdf8', fontWeight: 600 }}>{card.station}</span>
                </div>

                {card.corroboratesIncidentIds.length > 0 && (
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.65rem' }}>
                    <span style={{ color: '#64748b' }}>Corroborates:</span>
                    <span style={{ color: '#818cf8', fontWeight: 600 }}>{card.corroboratesIncidentIds.join(', ')}</span>
                  </div>
                )}

                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.65rem', marginTop: '2px' }}>
                  <span style={{ color: groundingColor(card.groundingStatus), display: 'flex', alignItems: 'center', gap: '3px' }}>
                    <CheckCircle2 size={11} /> {groundingLabel(card.groundingStatus)}
                  </span>
                  <span style={{ color: '#64748b', fontSize: '0.6rem' }}>Click to inspect</span>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* ── Card Detail Modal ─────────────────────────────────────────────────── */}
      {selectedCardForModal && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0, 0, 0, 0.75)',
            
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 10000,
            padding: '1rem',
          }}
        >
          <div
            style={{
              background: '#0f172a',
              border: '1px solid rgba(92, 200, 230, 0.35)',
              borderRadius: 'var(--radius-md)',
              maxWidth: '560px',
              width: '100%',
              padding: '1.5rem',
              boxShadow: '0 20px 50px rgba(0, 0, 0, 0.8)',
              display: 'flex',
              flexDirection: 'column',
              gap: '1rem',
              color: '#e2e8f0',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <div
                  style={{
                    background: getCategoryConfig(selectedCardForModal.type).fill,
                    color: getCategoryConfig(selectedCardForModal.type).color,
                    padding: '6px',
                    borderRadius: 'var(--radius-md)',
                  }}
                >
                  <Info size={18} />
                </div>
                <div>
                  <span style={{ fontSize: '0.65rem', fontWeight: 700, color: getCategoryConfig(selectedCardForModal.type).color, textTransform: 'uppercase' }}>
                    {getCategoryConfig(selectedCardForModal.type).label} DETAIL
                  </span>
                  <h3 style={{ fontSize: '1.05rem', fontWeight: 700, margin: '2px 0 0 0', color: '#f8fafc' }}>
                    {selectedCardForModal.title}
                  </h3>
                </div>
              </div>
              <button
                onClick={() => setSelectedCardForModal(null)}
                style={{ background: 'transparent', border: 'none', color: '#94a3b8', cursor: 'pointer' }}
              >
                <X size={18} />
              </button>
            </div>

            {/* Summary */}
            <div
              style={{
                fontSize: '0.85rem',
                lineHeight: '1.5',
                background: 'var(--bg-elevated)',
                padding: '1rem',
                borderRadius: 'var(--radius-md)',
                border: '1px solid var(--border-strong)',
              }}
            >
              {selectedCardForModal.summary}
            </div>

            {/* Citations & Metadata */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '8px', fontSize: '0.75rem' }}>
              <div style={{ background: 'var(--bg-card)', padding: '6px 10px', borderRadius: 'var(--radius-md)' }}>
                <div style={{ color: '#64748b' }}>Record ID:</div>
                <strong style={{ color: '#f8fafc' }}>{selectedCardForModal.id}</strong>
              </div>
              <div style={{ background: 'var(--bg-card)', padding: '6px 10px', borderRadius: 'var(--radius-md)' }}>
                <div style={{ color: '#64748b' }}>Precinct:</div>
                <strong style={{ color: '#38bdf8' }}>{selectedCardForModal.station}</strong>
              </div>
              <div style={{ background: 'var(--bg-card)', padding: '6px 10px', borderRadius: 'var(--radius-md)' }}>
                <div style={{ color: '#64748b' }}>Timestamp / Log:</div>
                <span style={{ color: '#cbd5e1' }}>{selectedCardForModal.timestamp || 'N/A'}</span>
              </div>
              <div style={{ background: 'var(--bg-card)', padding: '6px 10px', borderRadius: 'var(--radius-md)' }}>
                <div style={{ color: '#64748b' }}>Source table.record:</div>
                <code style={{ color: '#10b981', fontSize: '0.7rem' }}>{selectedCardForModal.citations[0]}</code>
              </div>
            </div>

            {/* Raw Metadata details */}
            <details style={{ fontSize: '0.7rem' }}>
              <summary style={{ color: '#818cf8', cursor: 'pointer', marginBottom: '4px' }}>
                View raw record attributes
              </summary>
              <pre
                style={{
                  background: '#040711',
                  padding: '8px',
                  borderRadius: 'var(--radius-md)',
                  color: '#94a3b8',
                  maxHeight: '140px',
                  overflowY: 'auto',
                }}
              >
                {JSON.stringify(selectedCardForModal.metadata, null, 2)}
              </pre>
            </details>

            {/* Footer Buttons */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '0.5rem' }}>
              <button
                onClick={() => {
                  togglePin(selectedCardForModal.id);
                }}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  padding: '6px 12px',
                  borderRadius: 'var(--radius-md)',
                  background: pinnedIds.has(selectedCardForModal.id) ? 'rgba(245, 158, 11, 0.2)' : 'var(--bg-elevated)',
                  color: pinnedIds.has(selectedCardForModal.id) ? '#fbbf24' : '#cbd5e1',
                  border: `1px solid ${pinnedIds.has(selectedCardForModal.id) ? '#f59e0b' : 'var(--border-strong)'}`,
                  fontSize: '0.75rem',
                  fontWeight: 600,
                  cursor: 'pointer',
                }}
              >
                <Pin size={13} /> {pinnedIds.has(selectedCardForModal.id) ? 'Pinned to Board' : 'Pin to Board'}
              </button>

              <button
                onClick={() => setSelectedCardForModal(null)}
                style={{
                  padding: '6px 14px',
                  borderRadius: 'var(--radius-md)',
                  background: '#5cc8e6',
                  color: '#fff',
                  border: 'none',
                  fontSize: '0.75rem',
                  fontWeight: 600,
                  cursor: 'pointer',
                }}
              >
                Done
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
