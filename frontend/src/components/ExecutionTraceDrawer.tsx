import React, { useEffect, useState, useMemo } from 'react';
import {
  X,
  Activity,
  BrainCircuit,
  Search,
  ShieldCheck,
  ShieldAlert,
  FileText,
  RefreshCw,
  Copy,
  ChevronDown,
  ChevronRight,
  Terminal,
  Clock,
} from 'lucide-react';
import { InvestigationTraceResponse } from '../types/investigation';

interface ExecutionTraceDrawerProps {
  runId: string;
  isOpen: boolean;
  onClose: () => void;
}

export const ExecutionTraceDrawer: React.FC<ExecutionTraceDrawerProps> = ({
  runId,
  isOpen,
  onClose,
}) => {
  const [loading, setLoading] = useState<boolean>(false);
  const [traceData, setTraceData] = useState<InvestigationTraceResponse | null>(null);
  const [copiedReceipt, setCopiedReceipt] = useState<string | null>(null);
  const [selectedAgentFilter, setSelectedAgentFilter] = useState<string>('ALL');
  const [searchFilter, setSearchFilter] = useState<string>('');
  const [traceError, setTraceError] = useState<string | null>(null);
  const [expandedSteps, setExpandedSteps] = useState<Record<number, boolean>>({ 0: true });

  // Fetch trace on open or runId change
  useEffect(() => {
    if (!isOpen || !runId) return;

    let isMounted = true;
    setLoading(true);

    fetch(`/api/investigations/${encodeURIComponent(runId)}/trace`)
      .then((res) => {
        if (!res.ok) {
          throw new Error(`HTTP ${res.status}: ${res.statusText}`);
        }
        return res.json() as Promise<InvestigationTraceResponse>;
      })
      .then((data) => {
        if (!isMounted) return;
        setTraceError(null);
        setTraceData(data);
      })
      .catch((err) => {
        if (!isMounted) return;
        // Never invent a trace: show that it could not be loaded.
        console.warn('Trace API fetch failed:', err);
        setTraceData(null);
        setTraceError(String(err?.message || err));
      })
      .finally(() => {
        if (isMounted) setLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, [isOpen, runId]);

  // Toggle step accordion
  const toggleStep = (idx: number) => {
    setExpandedSteps((prev) => ({
      ...prev,
      [idx]: !prev[idx],
    }));
  };

  // Copy receipt ID
  const handleCopy = (text: string) => {
    if (navigator?.clipboard) {
      navigator.clipboard.writeText(text);
      setCopiedReceipt(text);
      setTimeout(() => setCopiedReceipt(null), 2000);
    }
  };

  // Filter events
  const filteredEvents = useMemo(() => {
    if (!traceData?.events) return [];
    return traceData.events.filter((ev) => {
      if (selectedAgentFilter !== 'ALL' && ev.agent.toLowerCase() !== selectedAgentFilter.toLowerCase()) {
        return false;
      }
      if (searchFilter.trim()) {
        const q = searchFilter.toLowerCase();
        const inAgent = ev.agent.toLowerCase().includes(q);
        const inPhase = ev.phase.toLowerCase().includes(q);
        const inModel = ev.model.toLowerCase().includes(q);
        const inReceipt = ev.receipt_id.toLowerCase().includes(q);
        const inDetails = JSON.stringify(ev.details || {}).toLowerCase().includes(q);
        if (!inAgent && !inPhase && !inModel && !inReceipt && !inDetails) return false;
      }
      return true;
    });
  }, [traceData, selectedAgentFilter, searchFilter]);

  // Models that actually answered, from the recorded events only
  const usedModels = useMemo(() => {
    const acc: Record<string, { key: string; model: string; source: string; agents: string[]; calls: number }> = {};
    for (const ev of traceData?.events ?? []) {
      if (!ev.model) continue;
      const source = String(ev.details?.source ?? 'live');
      const key = `${ev.model}|${source}`;
      acc[key] = acc[key] ?? { key, model: ev.model, source, agents: [], calls: 0 };
      acc[key].calls += 1;
      if (!acc[key].agents.includes(ev.agent)) acc[key].agents.push(ev.agent);
    }
    return Object.values(acc);
  }, [traceData]);

  // Agent filter options come from the agents present in the trace.
  const agentNames = useMemo(
    () => ['ALL', ...Array.from(new Set((traceData?.events ?? []).map((e) => e.agent).filter(Boolean)))],
    [traceData],
  );

  // Zetaris queries and Nightshift receipts recorded in the trace.
  const zetarisQueries = useMemo(() => {
    const rows: Array<{ step: string; source: string; queries: number | null; ids: string[]; tables: string[] }> = [];
    for (const ev of traceData?.events ?? []) {
      const sql = ev.details?.sql;
      if (!sql) continue;
      rows.push({
        step: ev.phase,
        source: String(sql.source ?? 'unknown'),
        queries: typeof sql.queries === 'number' ? sql.queries : null,
        ids: Array.isArray(sql.query_ids) ? sql.query_ids.map(String) : [],
        tables: Array.isArray(sql.tables) ? sql.tables.map(String) : [],
      });
    }
    return rows;
  }, [traceData]);
  const receipts = useMemo(
    () => (traceData?.events ?? []).filter((e) => e.receipt_id).map((e) => ({ id: e.receipt_id, agent: e.agent, model: e.model })),
    [traceData],
  );

  if (!isOpen) return null;

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 9999,
        display: 'flex',
        justifyContent: 'flex-end',
      }}
    >
      {/* Backdrop */}
      <div
        onClick={onClose}
        style={{
          position: 'fixed',
          inset: 0,
          background: 'rgba(5, 8, 16, 0.75)',
          
          transition: 'opacity 0.25s ease',
        }}
      />

      {/* Slide-over Drawer */}
      <div
        style={{
          position: 'relative',
          width: '100%',
          maxWidth: '680px',
          height: '100%',
          background: '#090d16',
          borderLeft: '1px solid rgba(92, 200, 230, 0.35)',
          boxShadow: '-10px 0 50px rgba(0, 0, 0, 0.8)',
          display: 'flex',
          flexDirection: 'column',
          zIndex: 10000,
          color: '#e2e8f0',
        }}
      >
        {/* ── Drawer Header ─────────────────────────────────────────────────── */}
        <div
          style={{
            padding: '1.25rem 1.5rem',
            borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
            background: 'var(--bg-card)',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'flex-start',
          }}
        >
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
              <div
                style={{
                  background: 'var(--accent-green)',
                  padding: '6px',
                  borderRadius: 'var(--radius-md)',
                  color: '#fff',
                  display: 'flex',
                  alignItems: 'center',
                }}
              >
                <Terminal size={18} />
              </div>
              <h3 style={{ fontSize: '1.1rem', fontWeight: 700, margin: 0, color: '#f8fafc' }}>
                AEGIS EXECUTION TRACE INSPECTOR
              </h3>
              <span
                style={{
                  fontSize: '0.65rem',
                  fontWeight: 700,
                  padding: '2px 8px',
                  borderRadius: 'var(--radius-md)',
                  background: 'rgba(16, 185, 129, 0.15)',
                  color: '#10b981',
                  border: '1px solid rgba(16, 185, 129, 0.3)',
                }}
              >
                RECORDED TRACE
              </span>
            </div>
            <p style={{ fontSize: '0.75rem', color: '#94a3b8', margin: 0 }}>
              Chronological multi-agent timeline, read from logs/trace-{'<run_id>'}.jsonl
            </p>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginTop: '8px' }}>
              <span style={{ fontSize: '0.7rem', color: '#64748b' }}>Run ID:</span>
              <code
                style={{
                  fontSize: '0.75rem',
                  padding: '2px 8px',
                  borderRadius: 'var(--radius-sm)',
                  background: 'var(--bg-elevated)',
                  border: '1px solid var(--border-strong)',
                  color: '#38bdf8',
                  fontFamily: 'monospace',
                }}
              >
                {runId}
              </code>
              <button
                onClick={() => handleCopy(runId)}
                title="Copy Run ID"
                style={{ background: 'transparent', border: 'none', color: '#94a3b8', cursor: 'pointer', padding: 0 }}
              >
                <Copy size={13} />
              </button>
              {copiedReceipt === runId && (
                <span style={{ fontSize: '0.65rem', color: '#10b981' }}>Copied!</span>
              )}
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <button
              onClick={() => {
                setLoading(true);
                fetch(`/api/investigations/${encodeURIComponent(runId)}/trace`)
                  .then((res) => {
                    if (!res.ok) throw new Error(`HTTP ${res.status}`);
                    return res.json();
                  })
                  .then((d) => { setTraceError(null); setTraceData(d); })
                  .catch((e) => { setTraceData(null); setTraceError(String(e?.message || e)); })
                  .finally(() => setLoading(false));
              }}
              title="Refresh Trace"
              style={{
                background: 'var(--bg-elevated)',
                border: '1px solid var(--border-strong)',
                borderRadius: 'var(--radius-md)',
                padding: '6px',
                color: '#94a3b8',
                cursor: 'pointer',
              }}
            >
              <RefreshCw size={15} className={loading ? 'animate-spin' : ''} />
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
              <X size={16} />
            </button>
          </div>
        </div>

        {/* ── Models recorded in the trace ─────────────────────────────── */}
        <div
          style={{
            padding: '0.75rem 1.5rem',
            background: 'var(--bg-card)',
            borderBottom: '1px solid rgba(255, 255, 255, 0.06)',
            display: 'flex',
            flexDirection: 'column',
            gap: '6px',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: '0.7rem', fontWeight: 700, color: '#38bdf8', letterSpacing: '0.05em' }}>
              MODELS THAT ANSWERED IN THIS RUN (FROM THE TRACE):
            </span>
            <span style={{ fontSize: '0.65rem', color: '#10b981', display: 'flex', alignItems: 'center', gap: '4px' }}>
              {usedModels.length} model(s) recorded
            </span>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '6px', fontSize: '0.65rem' }}>
            {usedModels.length === 0 && (
              <div style={{ color: '#64748b' }}>No model calls recorded for this run.</div>
            )}
            {usedModels.map((m) => (
              <div key={m.key} style={{ background: 'var(--bg-elevated)', padding: '4px 8px', borderRadius: 'var(--radius-sm)', border: '1px solid rgba(92, 200, 230, 0.35)' }}>
                <span style={{ color: '#a5b4fc', fontWeight: 700 }}>{m.model}</span>
                <div style={{ color: '#64748b' }}>{m.agents.join(', ')} · {m.source}{m.calls > 1 ? ` · ${m.calls} calls` : ''}</div>
              </div>
            ))}
          </div>
        </div>

        {/* ── Zetaris query ids & receipts (from the trace, not hard-coded) ──── */}
        {traceData && (
          <details style={{ margin: '0.6rem 1.5rem 0', background: 'var(--bg-card)', borderRadius: 'var(--radius-md)', padding: '6px 10px', fontSize: '0.7rem' }}>
            <summary style={{ cursor: 'pointer', color: '#38bdf8', fontWeight: 700 }}>
              Zetaris queries ({zetarisQueries.reduce((n, r) => n + r.ids.length, 0)} query id(s)) &amp; model receipts ({receipts.length})
            </summary>
            <div style={{ marginTop: '6px', display: 'flex', flexDirection: 'column', gap: '4px', fontFamily: 'monospace', color: '#94a3b8' }}>
              {zetarisQueries.length === 0 && <div>No SQL retrieval step recorded in this trace.</div>}
              {zetarisQueries.map((r, i) => (
                <div key={i}>
                  <strong style={{ color: '#f8fafc' }}>{r.step}</strong> · source: {r.source}
                  {r.queries !== null ? ` · ${r.queries} query(ies)` : ''}
                  {r.tables.length > 0 && <div>tables: {r.tables.join(', ')}</div>}
                  <div>query ids: {r.ids.length ? r.ids.join(', ') : 'not recorded'}</div>
                </div>
              ))}
              <div style={{ borderTop: '1px solid rgba(255,255,255,0.06)', paddingTop: '4px' }}>
                {receipts.length === 0 && <div>No model receipts recorded.</div>}
                {receipts.map((r, i) => (
                  <div key={i}>{r.agent} · {r.model || 'model not recorded'} · receipt {r.id}</div>
                ))}
              </div>
            </div>
          </details>
        )}

        {traceError && (
          <div style={{ margin: '0 1.5rem', padding: '8px 12px', borderRadius: 'var(--radius-md)', background: 'rgba(244, 63, 94, 0.12)', color: '#fda4af', fontSize: '0.75rem' }}>
            Trace could not be loaded ({traceError}). Nothing is shown rather than a made-up trace.
          </div>
        )}

        {/* ── Filters & Search ───────────────────────────────────────────────── */}
        <div
          style={{
            padding: '0.6rem 1.5rem',
            background: 'var(--bg-card)',
            borderBottom: '1px solid rgba(255, 255, 255, 0.05)',
            display: 'flex',
            alignItems: 'center',
            gap: '10px',
            flexWrap: 'wrap',
          }}
        >
          <div style={{ display: 'flex', gap: '4px' }}>
            {agentNames.map((ag) => (
              <button
                key={ag}
                onClick={() => setSelectedAgentFilter(ag)}
                style={{
                  fontSize: '0.65rem',
                  fontWeight: 600,
                  padding: '3px 7px',
                  borderRadius: 'var(--radius-sm)',
                  background: selectedAgentFilter === ag ? 'rgba(92, 200, 230, 0.35)' : 'var(--bg-elevated)',
                  color: selectedAgentFilter === ag ? '#818cf8' : '#64748b',
                  border: `1px solid ${selectedAgentFilter === ag ? '#5cc8e6' : 'var(--border-strong)'}`,
                  cursor: 'pointer',
                  textTransform: 'capitalize',
                }}
              >
                {ag.replace('_', ' ')}
              </button>
            ))}
          </div>

          <div style={{ flex: 1, minWidth: '130px' }}>
            <input
              type="text"
              placeholder="Search steps, receipts, engines..."
              value={searchFilter}
              onChange={(e) => setSearchFilter(e.target.value)}
              style={{
                width: '100%',
                padding: '4px 8px',
                borderRadius: 'var(--radius-sm)',
                border: '1px solid var(--border-strong)',
                background: 'var(--bg-elevated)',
                color: '#fff',
                fontSize: '0.7rem',
              }}
            />
          </div>
        </div>

        {/* ── Chronological Agent Timeline ──────────────────────────────────── */}
        <div
          style={{
            flex: 1,
            overflowY: 'auto',
            padding: '1.25rem 1.5rem',
            display: 'flex',
            flexDirection: 'column',
            gap: '1rem',
          }}
        >
          {loading && (
            <div style={{ textAlign: 'center', padding: '2rem', color: '#94a3b8', fontSize: '0.85rem' }}>
              <Activity size={24} className="animate-spin" style={{ margin: '0 auto 8px auto', color: '#38bdf8' }} />
              Loading cryptographic execution trace...
            </div>
          )}

          {!loading && filteredEvents.length === 0 && (
            <div style={{ textAlign: 'center', padding: '2rem', color: '#64748b', fontSize: '0.8rem' }}>
              No trace events matched the selected agent or search filter.
            </div>
          )}

          {!loading &&
            filteredEvents.map((ev, idx) => {
              const isExpanded = !!expandedSteps[idx];
              const cfg = getAgentBadge(ev.agent);
              const IconComp = cfg.icon;

              return (
                <div
                  key={idx}
                  style={{
                    background: 'var(--bg-card)',
                    border: `1px solid ${cfg.border}`,
                    borderRadius: 'var(--radius-md)',
                    padding: '0.9rem',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '0.6rem',
                    transition: 'all 0.15s ease',
                  }}
                >
                  {/* Step Header */}
                  <div
                    onClick={() => toggleStep(idx)}
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      cursor: 'pointer',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <div
                        style={{
                          background: cfg.fill,
                          color: cfg.text,
                          border: `1px solid ${cfg.border}`,
                          padding: '6px',
                          borderRadius: 'var(--radius-md)',
                          display: 'flex',
                          alignItems: 'center',
                        }}
                      >
                        <IconComp size={16} />
                      </div>
                      <div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                          <span style={{ fontSize: '0.7rem', fontWeight: 800, color: cfg.text, textTransform: 'uppercase' }}>
                            TURN #{idx + 1}: {ev.agent.replace('_', ' ')}
                          </span>
                          <span
                            style={{
                              fontSize: '0.6rem',
                              fontWeight: 600,
                              padding: '1px 6px',
                              borderRadius: 'var(--radius-sm)',
                              background: 'rgba(255, 255, 255, 0.08)',
                              color: '#94a3b8',
                              textTransform: 'uppercase',
                            }}
                          >
                            {ev.phase}
                          </span>
                        </div>
                        <div style={{ fontSize: '0.65rem', color: '#64748b', display: 'flex', alignItems: 'center', gap: '6px', marginTop: '2px' }}>
                          <Clock size={11} /> {ev.timestamp}
                          {ev.details?.latency_ms ? (
                            <span style={{ color: '#38bdf8' }}>• Latency: {Math.round(Number(ev.details.latency_ms))}ms</span>
                          ) : null}
                          {ev.details?.source ? <span style={{ color: '#a5b4fc' }}>• {String(ev.details.source)}</span> : null}
                        </div>
                      </div>
                    </div>

                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <span
                        style={{
                          fontSize: '0.65rem',
                          padding: '2px 8px',
                          borderRadius: 'var(--radius-sm)',
                          background: 'rgba(92, 200, 230, 0.35)',
                          color: '#818cf8',
                          border: '1px solid rgba(92, 200, 230, 0.35)',
                          fontFamily: 'monospace',
                          fontWeight: 600,
                        }}
                      >
                        {ev.model || 'no model call'}
                      </span>
                      {isExpanded ? <ChevronDown size={16} color="#94a3b8" /> : <ChevronRight size={16} color="#94a3b8" />}
                    </div>
                  </div>

                  {/* Verifiable Receipt Bar */}
                  <div
                    style={{
                      background: 'rgba(0, 0, 0, 0.35)',
                      borderRadius: 'var(--radius-md)',
                      padding: '5px 8px',
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      fontSize: '0.65rem',
                      fontFamily: 'monospace',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: ev.receipt_id ? '#10b981' : '#64748b' }}>
                      <span style={{ color: '#94a3b8' }}>Receipt:</span>
                      <strong style={{ color: '#f8fafc' }}>{ev.receipt_id || 'none (no Nightshift call at this step)'}</strong>
                    </div>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        if (ev.receipt_id) handleCopy(ev.receipt_id);
                      }}
                      style={{
                        background: 'transparent',
                        border: 'none',
                        color: copiedReceipt === ev.receipt_id ? '#10b981' : '#64748b',
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '4px',
                        fontSize: '0.65rem',
                      }}
                    >
                      <Copy size={11} /> {copiedReceipt === ev.receipt_id ? 'Copied' : 'Copy'}
                    </button>
                  </div>

                  {/* Accordion Expanded Step Details */}
                  {isExpanded && (
                    <div
                      style={{
                        marginTop: '4px',
                        borderTop: '1px solid rgba(255, 255, 255, 0.06)',
                        paddingTop: '8px',
                        display: 'flex',
                        flexDirection: 'column',
                        gap: '6px',
                        fontSize: '0.75rem',
                      }}
                    >
                      {ev.details?.step && (
                        <div>
                          <span style={{ color: '#94a3b8' }}>Action Step: </span>
                          <strong style={{ color: '#38bdf8' }}>{ev.details.step}</strong>
                        </div>
                      )}

                      {ev.details?.meterless_engine && (
                        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                          <span style={{ color: '#94a3b8' }}>Meterless Engine: </span>
                          <span
                            style={{
                              fontSize: '0.65rem',
                              fontWeight: 700,
                              padding: '2px 6px',
                              borderRadius: 'var(--radius-sm)',
                              background: 'rgba(168, 85, 247, 0.2)',
                              color: '#c084fc',
                              border: '1px solid rgba(168, 85, 247, 0.4)',
                              textTransform: 'uppercase',
                            }}
                          >
                            {ev.details.meterless_engine}
                          </span>
                        </div>
                      )}

                      {ev.details?.sql && (
                        <div style={{ fontFamily: 'monospace', fontSize: '0.68rem', color: '#94a3b8' }}>
                          <span>Zetaris query ids: </span>
                          <strong style={{ color: '#f8fafc' }}>
                            {Array.isArray(ev.details.sql.query_ids) && ev.details.sql.query_ids.length ? ev.details.sql.query_ids.join(', ') : 'not recorded'}
                          </strong>
                          <span> · source: {String(ev.details.sql.source ?? 'unknown')}</span>
                        </div>
                      )}

                      {ev.details?.tables_queried && (
                        <div>
                          <span style={{ color: '#94a3b8' }}>Federated Zetaris Pushdown: </span>
                          <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap', marginTop: '3px' }}>
                            {ev.details.tables_queried.map((t: string) => (
                              <span
                                key={t}
                                style={{
                                  fontSize: '0.65rem',
                                  padding: '1px 5px',
                                  borderRadius: 'var(--radius-sm)',
                                  background: 'rgba(56, 189, 248, 0.15)',
                                  color: '#38bdf8',
                                }}
                              >
                                {t}
                              </span>
                            ))}
                          </div>
                        </div>
                      )}

                      {ev.details?.decision && (
                        <div style={{ background: 'rgba(16, 185, 129, 0.1)', padding: '6px 8px', borderRadius: 'var(--radius-sm)', borderLeft: '3px solid #10b981' }}>
                          <span style={{ color: '#10b981', fontWeight: 600 }}>Skeptic Decision: </span>
                          <span style={{ color: '#e2e8f0' }}>{ev.details.decision}</span>
                        </div>
                      )}

                      {ev.details?.notes && (
                        <div style={{ color: '#94a3b8', fontStyle: 'italic' }}>
                          "{ev.details.notes}"
                        </div>
                      )}

                      {/* Raw Details Inspector */}
                      <details style={{ marginTop: '4px' }}>
                        <summary style={{ fontSize: '0.65rem', color: '#64748b', cursor: 'pointer' }}>
                          View Raw Trace Payload
                        </summary>
                        <pre
                          style={{
                            background: '#040711',
                            padding: '8px',
                            borderRadius: 'var(--radius-sm)',
                            fontSize: '0.65rem',
                            color: '#94a3b8',
                            overflowX: 'auto',
                            maxHeight: '160px',
                            marginTop: '4px',
                          }}
                        >
                          {JSON.stringify(ev.details, null, 2)}
                        </pre>
                      </details>
                    </div>
                  )}
                </div>
              );
            })}
        </div>

        {/* ── Drawer Footer ─────────────────────────────────────────────────── */}
        <div
          style={{
            padding: '1rem 1.5rem',
            borderTop: '1px solid rgba(255, 255, 255, 0.08)',
            background: 'var(--bg-card)',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            fontSize: '0.75rem',
          }}
        >
          <div style={{ color: '#94a3b8', display: 'flex', alignItems: 'center', gap: '6px' }}>
            <ShieldCheck size={14} color="#10b981" />
            <span>Models, receipts and latencies are shown only where the run recorded them</span>
          </div>
          <button
            onClick={onClose}
            style={{
              padding: '6px 14px',
              borderRadius: 'var(--radius-md)',
              background: 'var(--bg-elevated)',
              border: '1px solid var(--border-strong)',
              color: '#fff',
              fontSize: '0.75rem',
              fontWeight: 600,
              cursor: 'pointer',
            }}
          >
            Close Trace
          </button>
        </div>
      </div>
    </div>
  );
};

// Helper: Agent Styling
function getAgentBadge(agent: string) {
  const ag = agent.toLowerCase();
  if (ag.includes('planner')) {
    return { border: '#b99cf5', fill: 'rgba(168, 85, 247, 0.2)', text: '#c084fc', icon: BrainCircuit };
  }
  if (ag.includes('finder')) {
    return { border: '#38bdf8', fill: 'rgba(56, 189, 248, 0.2)', text: '#7dd3fc', icon: Search };
  }
  if (ag.includes('skeptic')) {
    return { border: '#f43f5e', fill: 'rgba(244, 63, 94, 0.2)', text: '#fda4af', icon: ShieldAlert };
  }
  if (ag.includes('reporter')) {
    return { border: '#10b981', fill: 'rgba(16, 185, 129, 0.2)', text: '#6ee7b7', icon: FileText };
  }
  return { border: '#5cc8e6', fill: 'rgba(92, 200, 230, 0.35)', text: '#a5b4fc', icon: Activity };
}
