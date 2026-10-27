import React from 'react';
import {
  FileText,
  Printer,
  X,
  ShieldCheck,
  CheckCircle2,
  Scale,
  Cpu,
} from 'lucide-react';
import { InvestigationResponse } from '../types/investigation';

interface PinboardModalProps {
  isOpen: boolean;
  onClose: () => void;
  result: InvestigationResponse;
}

export const EvidencePinboardModal: React.FC<PinboardModalProps> = ({
  isOpen,
  onClose,
  result,
}) => {
  if (!isOpen) return null;

  const handlePrint = () => {
    window.print();
  };

  // Format date
  const generatedDate = result.timestamp
    ? new Date(result.timestamp * 1000).toLocaleString('en-US', {
        dateStyle: 'full',
        timeStyle: 'medium',
      })
    : new Date().toLocaleString();

  // Facts exactly as returned by the Reporter; nothing is substituted when the response has none.
  const facts = result.report?.facts ?? [];
  const links = result.candidate_links ?? [];
  const nSupported = links.filter((l) => l.validation_status === 'SUPPORTED').length;
  const nWeak = links.filter((l) => l.validation_status === 'WEAK').length;
  const nUnsupported = links.filter((l) => l.validation_status === 'UNSUPPORTED').length;
  const nNoVerifier = links.filter((l) => !l.validation_status).length;
  const objections = result.skeptic?.objections ?? [];
  const ungroundedObjections = objections.filter((o) => !o.grounded).length;
  const unverifiedStatements = result.report?.unverified_statements ?? [];
  const skepticStatus = result.skeptic?.review_status || 'not_run';
  const models = Array.from(new Set((result.agents ?? []).flatMap((a) => a.reported_models)));
  const engineOps = (result.engine_operations ?? []).reduce<Record<string, number>>((acc, o) => {
    acc[o.engine] = (acc[o.engine] ?? 0) + 1;
    return acc;
  }, {});

  return (
    <div
      className="court-dossier-modal-overlay"
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(5, 8, 16, 0.85)',
        
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 9999,
        padding: '1.5rem',
      }}
    >
      {/* Printable CSS Rules */}
      <style>{`
        @media print {
          body * {
            visibility: hidden !important;
          }
          .court-dossier-printable, .court-dossier-printable * {
            visibility: visible !important;
          }
          .court-dossier-printable {
            position: absolute !important;
            left: 0 !important;
            top: 0 !important;
            width: 100% !important;
            margin: 0 !important;
            padding: 20px !important;
            background: #ffffff !important;
            color: #000000 !important;
            box-shadow: none !important;
            border: none !important;
            font-family: 'Times New Roman', serif !important;
          }
          .no-print {
            display: none !important;
          }
          .print-border {
            border: 1px solid #333333 !important;
          }
          .print-header {
            border-bottom: 2px solid #000000 !important;
          }
        }
      `}</style>

      {/* Main Dossier Container */}
      <div
        className="court-dossier-printable"
        style={{
          background: '#0b1120',
          border: '1px solid rgba(92, 200, 230, 0.35)',
          borderRadius: 'var(--radius-md)',
          width: '100%',
          maxWidth: '920px',
          maxHeight: '92vh',
          display: 'flex',
          flexDirection: 'column',
          boxShadow: '0 25px 60px rgba(0, 0, 0, 0.8)',
          color: '#e2e8f0',
        }}
      >
        {/* ── Screen Header Bar (Hidden on Print) ────────────────────────────── */}
        <div
          className="no-print"
          style={{
            padding: '1.25rem 1.5rem',
            borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
            background: 'var(--bg-card)',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
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
              }}
            >
              <Scale size={20} />
            </div>
            <div>
              <h2 style={{ fontSize: '1.1rem', fontWeight: 800, margin: 0, color: '#f8fafc', letterSpacing: '0.02em' }}>
                AEGIS INVESTIGATION REPORT
              </h2>
              <span style={{ fontSize: '0.75rem', color: '#94a3b8' }}>
                Machine-generated analyst aid · not legal evidence · every claim must be checked against source records
              </span>
            </div>
          </div>

          <div style={{ display: 'flex', gap: '10px' }}>
            <button
              onClick={handlePrint}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                padding: '7px 14px',
                borderRadius: 'var(--radius-md)',
                background: 'var(--accent-green)',
                color: '#fff',
                border: 'none',
                fontSize: '0.8rem',
                fontWeight: 700,
                cursor: 'pointer',
                boxShadow: '0 2px 10px rgba(16, 185, 129, 0.3)',
              }}
            >
              <Printer size={15} /> Print / Export PDF
            </button>
            <button
              onClick={onClose}
              style={{
                background: 'var(--bg-elevated)',
                border: '1px solid var(--border-strong)',
                borderRadius: 'var(--radius-md)',
                padding: '6px',
                color: '#94a3b8',
                cursor: 'pointer',
              }}
            >
              <X size={18} />
            </button>
          </div>
        </div>

        {/* ── Dossier Document Body (Scrollable on Screen, Full Page on Print) ─── */}
        <div
          style={{
            padding: '2rem',
            overflowY: 'auto',
            display: 'flex',
            flexDirection: 'column',
            gap: '1.5rem',
            lineHeight: '1.5',
          }}
        >
          {/* Formal Law Enforcement Header */}
          <div
            className="print-header"
            style={{
              borderBottom: '2px solid rgba(92, 200, 230, 0.35)',
              paddingBottom: '1.25rem',
              textAlign: 'center',
            }}
          >
            <div style={{ fontSize: '0.75rem', fontWeight: 700, letterSpacing: '0.15em', color: '#94a3b8', textTransform: 'uppercase' }}>
              AEGIS CROSS-STATION CRIME INTELLIGENCE
            </div>
            <h1 style={{ fontSize: '1.4rem', fontWeight: 800, margin: '6px 0', color: '#f8fafc', letterSpacing: '0.04em' }}>
              INVESTIGATION REPORT (ANALYST DRAFT)
            </h1>
            <div
              style={{
                display: 'inline-block',
                fontSize: '0.7rem',
                fontWeight: 700,
                padding: '3px 12px',
                borderRadius: 'var(--radius-sm)',
                background: 'rgba(239, 68, 68, 0.15)',
                color: '#ef4444',
                border: '1px solid rgba(239, 68, 68, 0.3)',
                letterSpacing: '0.08em',
                marginTop: '4px',
              }}
            >
              {result.is_sample ? 'SAMPLE / REPLAYED DATA' : 'GENERATED FROM LIVE RUN'} · {result.data_mode}
            </div>
          </div>

          {/* Metadata Grid */}
          <div
            className="print-border"
            style={{
              background: 'var(--bg-card)',
              border: '1px solid var(--border-strong)',
              borderRadius: 'var(--radius-md)',
              padding: '1.2rem',
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(210px, 1fr))',
              gap: '1rem',
              fontSize: '0.8rem',
            }}
          >
            <div>
              <span style={{ color: '#64748b', display: 'block', fontSize: '0.7rem' }}>CASE REFERENCE / RUN ID:</span>
              <strong style={{ color: '#38bdf8', fontFamily: 'monospace' }}>{result.investigation_id}</strong>
            </div>
            <div>
              <span style={{ color: '#64748b', display: 'block', fontSize: '0.7rem' }}>PARTICIPATING PRECINCTS:</span>
              <strong style={{ color: '#f8fafc' }}>{result.stations_involved.length ? result.stations_involved.join(', ') : 'not available'}</strong>
            </div>
            <div>
              <span style={{ color: '#64748b', display: 'block', fontSize: '0.7rem' }}>DATA INTEGRATION LAYER:</span>
              <strong style={{ color: '#38bdf8' }}>{result.data_mode}{result.is_sample ? ' (not live Zetaris data)' : ''}</strong>
            </div>
            <div>
              <span style={{ color: '#64748b', display: 'block', fontSize: '0.7rem' }}>DATE OF GENERATION:</span>
              <span style={{ color: '#cbd5e1' }}>{generatedDate}</span>
            </div>
            <div>
              <span style={{ color: '#64748b', display: 'block', fontSize: '0.7rem' }}>LINK VERIFIER RESULTS:</span>
              <strong style={{ color: '#cbd5e1' }}>
                {links.length === 0 ? 'no links' : `${nSupported} supported, ${nWeak} weak, ${nUnsupported} unsupported, ${nNoVerifier} without verifier result`}
              </strong>
            </div>
            <div>
              <span style={{ color: '#64748b', display: 'block', fontSize: '0.7rem' }}>SKEPTIC REVIEW STATUS:</span>
              <strong style={{ color: '#38bdf8' }}>{skepticStatus}</strong>
            </div>
          </div>

          {/* Executive Summary */}
          <div>
            <h3
              style={{
                fontSize: '0.9rem',
                fontWeight: 800,
                color: '#38bdf8',
                letterSpacing: '0.05em',
                marginBottom: '0.6rem',
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
              }}
            >
              <FileText size={16} /> 1. EXECUTIVE SUMMARY
            </h3>
            <div
              style={{
                fontSize: '0.85rem',
                lineHeight: '1.6',
                background: 'rgba(0, 0, 0, 0.3)',
                padding: '1rem',
                borderRadius: 'var(--radius-md)',
                border: '1px solid rgba(255, 255, 255, 0.05)',
                color: '#cbd5e1',
              }}
            >
              {result.executive_summary}
            </div>
          </div>

          {/* Grounded Facts & Legal Citations */}
          <div>
            <h3
              style={{
                fontSize: '0.9rem',
                fontWeight: 800,
                color: '#10b981',
                letterSpacing: '0.05em',
                marginBottom: '0.6rem',
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
              }}
            >
              <CheckCircle2 size={16} /> 2. REPORTER FACTS WITH CITED RECORD IDS ({facts.length})
            </h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {facts.length === 0 && (
                <div style={{ fontSize: '0.8rem', color: '#64748b' }}>No facts available in this response.</div>
              )}
              {facts.map((fact, idx) => (
                <div
                  key={idx}
                  className="print-border"
                  style={{
                    background: 'var(--bg-card)',
                    borderLeft: '4px solid #10b981',
                    border: '1px solid var(--border-strong)',
                    borderRadius: 'var(--radius-md)',
                    padding: '0.85rem',
                    fontSize: '0.8rem',
                  }}
                >
                  <p style={{ margin: '0 0 6px 0', color: '#f8fafc', fontWeight: 500 }}>
                    <strong>§2.{idx + 1}</strong> {fact.statement}
                  </p>
                  <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', alignItems: 'center', fontSize: '0.7rem' }}>
                    <span style={{ color: '#64748b' }}>Cited source records:</span>
                    {fact.source_ids.map((sid) => (
                      <span
                        key={sid}
                        style={{
                          background: 'rgba(56, 189, 248, 0.15)',
                          color: '#38bdf8',
                          padding: '1px 6px',
                          borderRadius: 'var(--radius-sm)',
                          fontFamily: 'monospace',
                          fontWeight: 600,
                        }}
                      >
                        {sid}
                      </span>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Adversarial Skeptic Audit Section */}
          <div>
            <h3
              style={{
                fontSize: '0.9rem',
                fontWeight: 800,
                color: '#f43f5e',
                letterSpacing: '0.05em',
                marginBottom: '0.6rem',
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
              }}
            >
              <ShieldCheck size={16} /> 3. SKEPTIC REVIEW
            </h3>
            <div
              className="print-border"
              style={{
                background: 'var(--bg-card)',
                border: '1px solid var(--border-strong)',
                borderRadius: 'var(--radius-md)',
                padding: '1rem',
                fontSize: '0.8rem',
                display: 'flex',
                flexDirection: 'column',
                gap: '8px',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span>Skeptic review status:</span>
                <strong style={{ color: skepticStatus === 'not_run' ? '#64748b' : '#38bdf8' }}>{skepticStatus}</strong>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span>Objections citing unknown record ids / Reporter statements without support:</span>
                <strong style={{ color: '#38bdf8' }}>{result.skeptic ? ungroundedObjections : 'not available'} / {result.report ? unverifiedStatements.length : 'not available'}</strong>
              </div>
              {/* Skeptic Objections & Review Status */}
              <div style={{ marginTop: '6px', borderTop: '1px solid rgba(255,255,255,0.06)', paddingTop: '6px' }}>
                <span style={{ color: '#94a3b8', fontSize: '0.75rem', fontWeight: 600 }}>
                  Skeptic objections ({objections.length}):
                </span>
                {result.skeptic?.objections && result.skeptic.objections.length > 0 ? (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', marginTop: '4px' }}>
                    {result.skeptic.objections.map((obj, i) => (
                      <div
                        key={i}
                        style={{
                          background: 'rgba(0, 0, 0, 0.25)',
                          padding: '6px 8px',
                          borderRadius: 'var(--radius-sm)',
                          borderLeft: `3px solid ${obj.severity === 'high' ? '#f43f5e' : obj.severity === 'medium' ? '#f59e0b' : '#38bdf8'}`,
                          fontSize: '0.75rem',
                        }}
                      >
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <span style={{ fontWeight: 600, color: '#f8fafc' }}>
                            [{obj.kind.toUpperCase()}] {obj.description}
                          </span>
                          <span
                            style={{
                              fontSize: '0.65rem',
                              padding: '1px 5px',
                              borderRadius: 'var(--radius-sm)',
                              background: obj.open ? 'rgba(244, 63, 94, 0.2)' : 'rgba(148, 163, 184, 0.2)',
                              color: obj.open ? '#f43f5e' : '#94a3b8',
                            }}
                          >
                            {obj.open ? 'OPEN' : 'SUPERSEDED'}{obj.grounded ? '' : ' · cites unknown ids'}
                          </span>
                        </div>
                        {obj.cited_ids?.length > 0 && (
                          <div style={{ fontSize: '0.65rem', color: '#64748b', marginTop: '2px' }}>
                            Cited Records: {obj.cited_ids.join(', ')}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                ) : (
                  <div style={{ fontSize: '0.75rem', color: '#64748b', marginTop: '3px' }}>
                    {result.skeptic ? 'No objections recorded.' : 'Skeptic did not run (not_run); no review is available.'}
                  </div>
                )}
              </div>

              {result.contradictions_and_limitations?.length > 0 && (
                <div style={{ marginTop: '4px', borderTop: '1px solid rgba(255,255,255,0.06)', paddingTop: '6px' }}>
                  <span style={{ color: '#94a3b8', fontSize: '0.75rem', fontWeight: 600 }}>Contradictions and limitations:</span>
                  <ul style={{ margin: '4px 0 0 16px', padding: 0, color: '#cbd5e1', fontSize: '0.75rem' }}>
                    {result.contradictions_and_limitations.map((c, i) => (
                      <li key={i}>{c}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </div>

          {/* Model Lanes & Meterless Engine Attestation */}
          <div>
            <h3
              style={{
                fontSize: '0.9rem',
                fontWeight: 800,
                color: '#b99cf5',
                letterSpacing: '0.05em',
                marginBottom: '0.6rem',
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
              }}
            >
              <Cpu size={16} /> 4. MODELS AND ENGINES REPORTED IN THIS RUN
            </h3>
            <div
              className="print-border"
              style={{
                background: 'var(--bg-card)',
                border: '1px solid var(--border-strong)',
                borderRadius: 'var(--radius-md)',
                padding: '1rem',
                fontSize: '0.75rem',
                display: 'grid',
                gridTemplateColumns: 'repeat(2, 1fr)',
                gap: '8px',
              }}
            >
              <div>
                <strong style={{ color: '#f8fafc' }}>Models that answered (per agent, from the response):</strong>
                <ul style={{ margin: '4px 0 0 16px', padding: 0, color: '#94a3b8' }}>
                  {(result.agents ?? []).length === 0 && <li>not available</li>}
                  {(result.agents ?? []).map((a) => (
                    <li key={a.agent}>{a.reported_models.join(', ') || 'none recorded'} ({a.agent}{a.fallback_used ? ', fallback used' : ''})</li>
                  ))}
                </ul>
                {models.length === 0 && <div style={{ color: '#64748b' }}>No model calls reported.</div>}
              </div>
              <div>
                <strong style={{ color: '#f8fafc' }}>Engine operations recorded:</strong>
                <ul style={{ margin: '4px 0 0 16px', padding: 0, color: '#94a3b8' }}>
                  {Object.keys(engineOps).length === 0 && <li>not available</li>}
                  {Object.entries(engineOps).map(([e, n]) => (
                    <li key={e}>{e}: {n} op(s)</li>
                  ))}
                </ul>
              </div>
            </div>
          </div>

          {/* Legal Chain of Custody & Sign-off Block */}
          <div
            className="print-border"
            style={{
              borderTop: '2px solid rgba(92, 200, 230, 0.35)',
              paddingTop: '1.25rem',
              display: 'flex',
              flexDirection: 'column',
              gap: '1rem',
            }}
          >
            <div style={{ fontSize: '0.75rem', color: '#94a3b8', lineHeight: '1.5', fontStyle: 'italic' }}>
              <strong>NOTICE:</strong> This report was generated by the AEGIS analyst-assist pipeline. It is an investigative
              lead aid, not evidence and not a legal certification. Link verifier results, Skeptic status and model names above
              are taken from this run&apos;s response; where a value is not available it is shown as such. Every cited record id
              should be checked against the source system before any action is taken.
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
