import React, { useState, useMemo } from 'react';
import {
  Share2,
  Shield,
  User,
  Car,
  Microscope,
  Search,
  X,
  ExternalLink,
  Layers,
} from 'lucide-react';
import {
  CandidateLink,
  GraphEntityNode,
  GraphEdge,
  EntityType,
} from '../types/investigation';

interface InteractiveGraphProps {
  links?: CandidateLink[];
  candidateLinks?: CandidateLink[];
  candidateIncidents?: Record<string, any>[];
  incidents?: any[];
  supportingEvidence?: {
    cctv_reports?: Record<string, any>[];
    witness_reports?: Record<string, any>[];
    forensic_reports?: Record<string, any>[];
    newspaper_reports?: Record<string, any>[];
  };
  selectedIncidentId?: string;
  onSelectIncident?: (incidentId: string) => void;
}

export const InteractiveGraphCanvas: React.FC<InteractiveGraphProps> = ({
  links,
  candidateLinks,
  candidateIncidents,
  incidents,
  supportingEvidence,
  selectedIncidentId: externalSelectedId,
  onSelectIncident,
}) => {
  // Normalize input props
  const allLinks = useMemo(() => candidateLinks || links || [], [candidateLinks, links]);
  const allIncidents = useMemo(() => candidateIncidents || incidents || [], [candidateIncidents, incidents]);
  const evidence = useMemo(() => supportingEvidence || {}, [supportingEvidence]);

  // Filtering & Selection state
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(externalSelectedId || null);
  const [hoveredNodeId, setHoveredNodeId] = useState<string | null>(null);
  const [confidenceThreshold, setConfidenceThreshold] = useState<number>(0.4);
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [selectedStations, setSelectedStations] = useState<string[]>(['NORTH', 'CENTRAL', 'RIVERSIDE']);
  const [enabledEntityTypes, setEnabledEntityTypes] = useState<Record<EntityType, boolean>>({
    incident: true,
    suspect: true,
    vehicle: true,
    evidence: true,
  });

  // Toggle station filter
  const toggleStation = (station: string) => {
    if (selectedStations.includes(station)) {
      if (selectedStations.length > 1) {
        setSelectedStations(selectedStations.filter((s) => s !== station));
      }
    } else {
      setSelectedStations([...selectedStations, station]);
    }
  };

  // Toggle entity type filter
  const toggleEntityType = (type: EntityType) => {
    setEnabledEntityTypes((prev) => ({
      ...prev,
      [type]: !prev[type],
    }));
  };

  // Extract Multi-Entity Graph Nodes and Edges
  const { nodes, edges } = useMemo(() => {
    const nodeList: GraphEntityNode[] = [];
    const edgeList: GraphEdge[] = [];
    const nodeMap = new Map<string, GraphEntityNode>();

    // 1. Incident Nodes
    allIncidents.forEach((inc) => {
      const incId = inc.incident_id || String(inc.id || 'INC-UNKNOWN');
      const node: GraphEntityNode = {
        id: incId,
        type: 'incident',
        label: incId,
        station: inc.station_id || 'UNKNOWN',
        crimeType: inc.crime_type || 'BURGLARY',
        description: inc.method_description || inc.location_description || 'Incident Record',
        status: inc.status || 'OPEN',
        metadata: inc,
      };
      nodeList.push(node);
      nodeMap.set(incId, node);
    });

    // 2. Incident-to-Incident Edges from Candidate Links
    allLinks.forEach((link) => {
      const status = link.validation_status || (link.confidence_score >= 0.7 ? 'SUPPORTED' : link.confidence_score >= 0.4 ? 'WEAK' : 'UNSUPPORTED');
      edgeList.push({
        id: link.link_id || `edge-${link.source_incident_id}-${link.target_incident_id}`,
        source: link.source_incident_id,
        target: link.target_incident_id,
        type: 'cross_station_link',
        confidence: link.confidence_score,
        status: status as 'SUPPORTED' | 'WEAK' | 'UNSUPPORTED',
        basis: link.similarity_basis || link.confidence_rationale,
        supporting_evidence_ids: link.supporting_evidence_ids,
      });

      // Extract shared attributes (Suspects / Vehicles)
      if (link.shared_attributes && link.shared_attributes.length > 0) {
        link.shared_attributes.forEach((attr, idx) => {
          const attrLower = attr.attribute.toLowerCase();
          const isSuspect = attrLower.includes('suspect') || attrLower.includes('person') || attrLower.includes('operator');
          const isVehicle = attrLower.includes('vehicle') || attrLower.includes('car') || attrLower.includes('van') || attrLower.includes('truck');

          if (isSuspect || isVehicle) {
            const entType: EntityType = isSuspect ? 'suspect' : 'vehicle';
            const entityId = `${entType.toUpperCase()}-${attr.value.replace(/[^a-zA-Z0-9]/g, '-').slice(0, 16)}-${idx}`;

            if (!nodeMap.has(entityId)) {
              const entNode: GraphEntityNode = {
                id: entityId,
                type: entType,
                label: attr.value,
                station: link.stations_involved?.[0] || 'MULTI-STATION',
                description: `${attr.attribute}: ${attr.value} (${attr.match_type || 'Cross-station signature'})`,
                status: 'CORRELATED',
                confidence: link.confidence_score,
                metadata: { ...attr, link_id: link.link_id },
              };
              nodeList.push(entNode);
              nodeMap.set(entityId, entNode);
            }

            // Connect to source and target incidents
            edgeList.push({
              id: `edge-${link.source_incident_id}-${entityId}`,
              source: link.source_incident_id,
              target: entityId,
              type: isSuspect ? 'involves_suspect' : 'involves_vehicle',
              confidence: link.confidence_score,
              status: status as 'SUPPORTED' | 'WEAK' | 'UNSUPPORTED',
              basis: `Direct correlation: ${attr.value}`,
            });

            edgeList.push({
              id: `edge-${link.target_incident_id}-${entityId}`,
              source: link.target_incident_id,
              target: entityId,
              type: isSuspect ? 'involves_suspect' : 'involves_vehicle',
              confidence: link.confidence_score,
              status: status as 'SUPPORTED' | 'WEAK' | 'UNSUPPORTED',
              basis: `Direct correlation: ${attr.value}`,
            });
          }
        });
      }
    });

    // 3. Evidence Items from Supporting Evidence (CCTV, Forensic, Witness, News)
    const addEvidenceNodes = (
      items: Record<string, any>[] | undefined,
      category: 'cctv' | 'witness' | 'forensic' | 'newspaper',
      idKey: string,
      labelPrefix: string,
      defaultStation: string
    ) => {
      if (!items || !items.length) return;
      items.forEach((item) => {
        const evId = item[idKey] || item.id || `${labelPrefix}-${Math.random().toString(36).substr(2, 6)}`;
        if (!nodeMap.has(evId)) {
          const evNode: GraphEntityNode = {
            id: evId,
            type: 'evidence',
            label: evId,
            station: item.station_id || item.precinct || defaultStation,
            crimeType: category.toUpperCase(),
            description: item.description || item.observations || item.statement || item.headline || 'Corroborating record',
            status: 'RETRIEVED_RECORD',
            confidence: 0,
            metadata: { ...item, category },
          };
          nodeList.push(evNode);
          nodeMap.set(evId, evNode);
        }

        // Connect evidence to corresponding incident
        const connectedIncidentId = item.incident_id || item.referenced_incident_id || item.station_incident_id;
        if (connectedIncidentId && nodeMap.has(connectedIncidentId)) {
          edgeList.push({
            id: `edge-${connectedIncidentId}-${evId}`,
            source: connectedIncidentId,
            target: evId,
            type: 'supported_by_evidence',
            confidence: 0,
            status: 'SUPPORTED',
            basis: `Retrieved ${category} record that cites this incident`,
          });
        }

        // Connect evidence to candidate links that cite this evidence
        allLinks.forEach((link) => {
          if (link.supporting_evidence_ids && link.supporting_evidence_ids.includes(evId)) {
            if (nodeMap.has(link.source_incident_id)) {
              const eId1 = `edge-${link.source_incident_id}-${evId}`;
              if (!edgeList.some((e) => e.id === eId1)) {
                edgeList.push({
                  id: eId1,
                  source: link.source_incident_id,
                  target: evId,
                  type: 'supported_by_evidence',
                  confidence: 0,
                  status: 'SUPPORTED',
                  basis: `Cited as supporting evidence for ${link.link_id} (verifier status is on the link)`,
                });
              }
            }
            if (nodeMap.has(link.target_incident_id)) {
              const eId2 = `edge-${link.target_incident_id}-${evId}`;
              if (!edgeList.some((e) => e.id === eId2)) {
                edgeList.push({
                  id: eId2,
                  source: link.target_incident_id,
                  target: evId,
                  type: 'supported_by_evidence',
                  confidence: 0,
                  status: 'SUPPORTED',
                  basis: `Cited as supporting evidence for ${link.link_id} (verifier status is on the link)`,
                });
              }
            }
          }
        });
      });
    };

    addEvidenceNodes(evidence.cctv_reports, 'cctv', 'cctv_report_id', 'CCTV', 'CENTRAL');
    addEvidenceNodes(evidence.forensic_reports, 'forensic', 'report_id', 'FOR', 'NORTH');
    addEvidenceNodes(evidence.witness_reports, 'witness', 'statement_id', 'WIT', 'CENTRAL');
    addEvidenceNodes(evidence.newspaper_reports, 'newspaper', 'article_id', 'NEWS', 'RIVERSIDE');

    // No entities are invented: only incidents, evidence and links present in the response are drawn.

    return { nodes: nodeList, edges: edgeList };
  }, [allIncidents, allLinks, evidence]);

  // Apply filters
  const filteredNodes = useMemo(() => {
    return nodes.filter((node) => {
      // 1. Entity type enabled
      if (!enabledEntityTypes[node.type]) return false;

      // 2. Station filter (keep multi-station or matches selected stations)
      if (node.station && node.station !== 'UNKNOWN' && node.station !== 'MULTI-STATION' && node.station !== 'CROSS-PRECINCT') {
        const isMatched = selectedStations.some((st) => node.station?.toUpperCase().includes(st));
        if (!isMatched) return false;
      }

      // 3. Search query
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        const matchesId = node.id.toLowerCase().includes(q);
        const matchesLabel = node.label.toLowerCase().includes(q);
        const matchesDesc = (node.description || '').toLowerCase().includes(q);
        if (!matchesId && !matchesLabel && !matchesDesc) return false;
      }

      return true;
    });
  }, [nodes, enabledEntityTypes, selectedStations, searchQuery]);

  const filteredNodeIds = useMemo(() => new Set(filteredNodes.map((n) => n.id)), [filteredNodes]);

  const filteredEdges = useMemo(() => {
    return edges.filter((edge) => {
      // Must connect active filtered nodes
      if (!filteredNodeIds.has(edge.source) || !filteredNodeIds.has(edge.target)) return false;

      // Confidence threshold
      if (edge.confidence < confidenceThreshold) return false;

      return true;
    });
  }, [edges, filteredNodeIds, confidenceThreshold]);

  // Compute Layout Coordinates (SVG Canvas 960 x 520)
  const nodePositions = useMemo(() => {
    const positions = new Map<string, { x: number; y: number }>();
    const width = 940;

    // Partition nodes by category/station for tactical structure
    const suspectsAndVehicles = filteredNodes.filter((n) => n.type === 'suspect' || n.type === 'vehicle');
    const incidentNodes = filteredNodes.filter((n) => n.type === 'incident');
    const evidenceNodes = filteredNodes.filter((n) => n.type === 'evidence');

    // Row 1: Suspects and Vehicles (Center top hub)
    suspectsAndVehicles.forEach((node, idx) => {
      const total = suspectsAndVehicles.length;
      const spacing = width / (total + 1);
      positions.set(node.id, {
        x: spacing * (idx + 1),
        y: 80,
      });
    });

    // Row 2: Incidents (Structured across stations)
    // Group incidents by station: North (left), Central (middle), Riverside (right)
    const northInc = incidentNodes.filter((n) => (n.station || '').toUpperCase().includes('NORTH'));
    const centralInc = incidentNodes.filter((n) => (n.station || '').toUpperCase().includes('CENTRAL'));
    const riversideInc = incidentNodes.filter((n) => (n.station || '').toUpperCase().includes('RIVERSIDE'));
    const otherInc = incidentNodes.filter(
      (n) => !northInc.includes(n) && !centralInc.includes(n) && !riversideInc.includes(n)
    );

    const stationColumns = [
      { name: 'NORTH', nodes: northInc, cx: 200 },
      { name: 'CENTRAL', nodes: centralInc, cx: 480 },
      { name: 'RIVERSIDE', nodes: [...riversideInc, ...otherInc], cx: 760 },
    ];

    stationColumns.forEach((col) => {
      col.nodes.forEach((node, idx) => {
        const total = col.nodes.length;
        const startY = 220;
        const gapY = total > 1 ? 70 : 0;
        positions.set(node.id, {
          x: col.cx + (idx % 2 === 1 ? 40 : -40),
          y: startY + idx * gapY,
        });
      });
    });

    // Row 3: Evidence items (Lower section)
    evidenceNodes.forEach((node, idx) => {
      const total = evidenceNodes.length;
      const spacing = width / (total + 1);
      positions.set(node.id, {
        x: spacing * (idx + 1),
        y: 420,
      });
    });

    return positions;
  }, [filteredNodes]);

  // Currently selected node object
  const activeSelectedNode = useMemo(() => {
    if (!selectedNodeId) return null;
    return nodes.find((n) => n.id === selectedNodeId) || null;
  }, [selectedNodeId, nodes]);

  // Edges connected to hovered or selected node
  const highlightedEdgeIds = useMemo(() => {
    const targetId = hoveredNodeId || selectedNodeId;
    if (!targetId) return new Set<string>();
    const set = new Set<string>();
    filteredEdges.forEach((e) => {
      if (e.source === targetId || e.target === targetId) {
        set.add(e.id);
      }
    });
    return set;
  }, [hoveredNodeId, selectedNodeId, filteredEdges]);

  // Helper color functions
  const getNodeColor = (type: EntityType) => {
    switch (type) {
      case 'incident':
        return { border: '#6366f1', fill: 'rgba(99, 102, 241, 0.25)', text: '#e0e7ff', icon: Shield };
      case 'suspect':
        return { border: '#f43f5e', fill: 'rgba(244, 63, 94, 0.25)', text: '#ffe4e6', icon: User };
      case 'vehicle':
        return { border: '#06b6d4', fill: 'rgba(6, 182, 212, 0.25)', text: '#cffafe', icon: Car };
      case 'evidence':
        return { border: '#10b981', fill: 'rgba(16, 185, 129, 0.25)', text: '#d1fae5', icon: Microscope };
    }
  };

  const getEdgeStroke = (edge: GraphEdge) => {
    if (edge.status === 'SUPPORTED') return '#10b981'; // emerald
    if (edge.status === 'WEAK') return '#f59e0b'; // amber
    return '#f43f5e'; // rose
  };

  return (
    <div
      style={{
        background: 'var(--bg-card, #0f172a)',
        border: '1px solid var(--border-subtle, rgba(148, 163, 184, 0.15))',
        borderRadius: '14px',
        padding: '1.25rem',
        boxShadow: '0 8px 30px rgba(0, 0, 0, 0.35)',
        display: 'flex',
        flexDirection: 'column',
        gap: '1rem',
      }}
    >
      {/* ── Header & Toolbar ─────────────────────────────────────────────────── */}
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
              background: 'linear-gradient(135deg, #6366f1, #a855f7)',
              padding: '8px',
              borderRadius: '10px',
              color: '#fff',
              display: 'flex',
              alignItems: 'center',
              boxShadow: '0 0 15px rgba(168, 85, 247, 0.4)',
            }}
          >
            <Share2 size={20} />
          </div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <h3 style={{ fontSize: '1.05rem', fontWeight: 700, margin: 0, letterSpacing: '0.02em', color: '#f8fafc' }}>
                PALANTIR GOTHAM MULTI-ENTITY KNOWLEDGE GRAPH
              </h3>
              <span
                style={{
                  fontSize: '0.65rem',
                  fontWeight: 700,
                  padding: '2px 8px',
                  borderRadius: '12px',
                  background: 'rgba(16, 185, 129, 0.15)',
                  color: 'var(--accent-emerald, #10b981)',
                  border: '1px solid rgba(16, 185, 129, 0.3)',
                }}
              >
                LIVE DIRECTED SVG
              </span>
            </div>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary, #94a3b8)' }}>
              Cross-Jurisdiction Linkages · Suspects · Vehicles · Corroborating Forensic Evidence
            </span>
          </div>
        </div>

        {/* Global Stats */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', fontSize: '0.75rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: '#94a3b8' }}>
            <Layers size={14} color="#6366f1" />
            <span>Entities: <strong style={{ color: '#f8fafc' }}>{filteredNodes.length}</strong></span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: '#94a3b8' }}>
            <Share2 size={14} color="#10b981" />
            <span>Linkages: <strong style={{ color: '#f8fafc' }}>{filteredEdges.length}</strong></span>
          </div>
        </div>
      </div>

      {/* ── Interactive Filter Controls ────────────────────────────────────────── */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: '12px',
          background: 'rgba(15, 23, 42, 0.6)',
          padding: '0.75rem 1rem',
          borderRadius: '10px',
          border: '1px solid rgba(255, 255, 255, 0.05)',
        }}
      >
        {/* Search */}
        <div style={{ position: 'relative', minWidth: '180px', flex: '1 1 180px' }}>
          <Search size={14} style={{ position: 'absolute', left: '10px', top: '50%', transform: 'translateY(-50%)', color: '#64748b' }} />
          <input
            type="text"
            placeholder="Search entities, suspects, toolmarks..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            style={{
              width: '100%',
              padding: '6px 10px 6px 30px',
              borderRadius: '6px',
              border: '1px solid rgba(148, 163, 184, 0.2)',
              background: 'rgba(30, 41, 59, 0.8)',
              color: '#fff',
              fontSize: '0.75rem',
            }}
          />
        </div>

        {/* Station Filter Pills */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <span style={{ fontSize: '0.7rem', color: '#94a3b8', fontWeight: 600 }}>PRECINCTS:</span>
          {['NORTH', 'CENTRAL', 'RIVERSIDE'].map((st) => {
            const active = selectedStations.includes(st);
            return (
              <button
                key={st}
                onClick={() => toggleStation(st)}
                style={{
                  fontSize: '0.65rem',
                  fontWeight: 700,
                  padding: '3px 8px',
                  borderRadius: '6px',
                  background: active ? 'rgba(99, 102, 241, 0.3)' : 'rgba(30, 41, 59, 0.4)',
                  color: active ? '#818cf8' : '#64748b',
                  border: `1px solid ${active ? '#6366f1' : 'rgba(148, 163, 184, 0.2)'}`,
                  cursor: 'pointer',
                  transition: 'all 0.15s ease',
                }}
              >
                {st}
              </button>
            );
          })}
        </div>

        {/* Entity Type Toggles */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <span style={{ fontSize: '0.7rem', color: '#94a3b8', fontWeight: 600 }}>ENTITIES:</span>
          {(['incident', 'suspect', 'vehicle', 'evidence'] as EntityType[]).map((type) => {
            const active = enabledEntityTypes[type];
            const cfg = getNodeColor(type);
            const IconComponent = cfg.icon;
            return (
              <button
                key={type}
                onClick={() => toggleEntityType(type)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '4px',
                  fontSize: '0.65rem',
                  fontWeight: 600,
                  padding: '3px 8px',
                  borderRadius: '6px',
                  background: active ? cfg.fill : 'rgba(30, 41, 59, 0.4)',
                  color: active ? cfg.text : '#64748b',
                  border: `1px solid ${active ? cfg.border : 'rgba(148, 163, 184, 0.2)'}`,
                  cursor: 'pointer',
                  textTransform: 'capitalize',
                  transition: 'all 0.15s ease',
                }}
              >
                <IconComponent size={12} />
                {type}
              </button>
            );
          })}
        </div>

        {/* Confidence Threshold Slider */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{ fontSize: '0.7rem', color: '#94a3b8' }}>
            Min Confidence: <strong style={{ color: '#38bdf8' }}>{Math.round(confidenceThreshold * 100)}%</strong>
          </span>
          <input
            type="range"
            min="0"
            max="1"
            step="0.05"
            value={confidenceThreshold}
            onChange={(e) => setConfidenceThreshold(parseFloat(e.target.value))}
            style={{ width: '80px', cursor: 'pointer' }}
          />
        </div>
      </div>

      {/* ── Main Knowledge Graph SVG Canvas & Inspector ───────────────────────── */}
      <div style={{ display: 'flex', gap: '1rem', position: 'relative' }}>
        {/* SVG Viewport */}
        <div
          style={{
            flex: 1,
            minHeight: '480px',
            background: 'radial-gradient(ellipse at 50% 50%, #0d1527 0%, #060913 100%)',
            borderRadius: '12px',
            border: '1px solid rgba(99, 102, 241, 0.25)',
            position: 'relative',
            overflow: 'hidden',
          }}
        >
          {/* Tactical Crosshair Background Overlay */}
          <div
            style={{
              position: 'absolute',
              inset: 0,
              backgroundImage: `
                linear-gradient(to right, rgba(255, 255, 255, 0.03) 1px, transparent 1px),
                linear-gradient(to bottom, rgba(255, 255, 255, 0.03) 1px, transparent 1px)
              `,
              backgroundSize: '40px 40px',
              pointerEvents: 'none',
            }}
          />

          {/* Station Column Zone Labels */}
          <div
            style={{
              position: 'absolute',
              top: '8px',
              left: 0,
              right: 0,
              display: 'flex',
              justifyContent: 'space-around',
              pointerEvents: 'none',
              padding: '0 20px',
              zIndex: 1,
            }}
          >
            <span style={{ fontSize: '0.65rem', fontWeight: 700, color: 'rgba(56, 189, 248, 0.4)', letterSpacing: '0.1em' }}>
              SECTOR 1: NORTH PRECINCT
            </span>
            <span style={{ fontSize: '0.65rem', fontWeight: 700, color: 'rgba(168, 85, 247, 0.4)', letterSpacing: '0.1em' }}>
              SECTOR 2: CENTRAL HEADQUARTERS
            </span>
            <span style={{ fontSize: '0.65rem', fontWeight: 700, color: 'rgba(16, 185, 129, 0.4)', letterSpacing: '0.1em' }}>
              SECTOR 3: RIVERSIDE PRECINCT
            </span>
          </div>

          {/* SVG Engine */}
          <svg
            viewBox="0 0 940 480"
            style={{ width: '100%', height: '100%', minHeight: '480px', display: 'block' }}
          >
            <defs>
              {/* Arrow Markers for Directed Edges */}
              <marker
                id="arrow-emerald"
                viewBox="0 0 10 10"
                refX="20"
                refY="5"
                markerWidth="6"
                markerHeight="6"
                orient="auto-start-reverse"
              >
                <path d="M 0 0 L 10 5 L 0 10 z" fill="#10b981" />
              </marker>
              <marker
                id="arrow-amber"
                viewBox="0 0 10 10"
                refX="20"
                refY="5"
                markerWidth="6"
                markerHeight="6"
                orient="auto-start-reverse"
              >
                <path d="M 0 0 L 10 5 L 0 10 z" fill="#f59e0b" />
              </marker>
              <marker
                id="arrow-rose"
                viewBox="0 0 10 10"
                refX="20"
                refY="5"
                markerWidth="6"
                markerHeight="6"
                orient="auto-start-reverse"
              >
                <path d="M 0 0 L 10 5 L 0 10 z" fill="#f43f5e" />
              </marker>
              <marker
                id="arrow-cyan"
                viewBox="0 0 10 10"
                refX="20"
                refY="5"
                markerWidth="6"
                markerHeight="6"
                orient="auto-start-reverse"
              >
                <path d="M 0 0 L 10 5 L 0 10 z" fill="#06b6d4" />
              </marker>
            </defs>

            {/* Render Directed Edges */}
            {filteredEdges.map((edge) => {
              const srcPos = nodePositions.get(edge.source);
              const tgtPos = nodePositions.get(edge.target);
              if (!srcPos || !tgtPos) return null;

              const isHighlighted = highlightedEdgeIds.has(edge.id);
              const strokeColor = getEdgeStroke(edge);
              const strokeWidth = isHighlighted ? 3 : edge.status === 'SUPPORTED' ? 2 : 1.5;
              const opacity = isHighlighted ? 1 : hoveredNodeId || selectedNodeId ? 0.25 : 0.75;

              // Smooth curved bezier line
              const dx = tgtPos.x - srcPos.x;
              const dy = tgtPos.y - srcPos.y;
              const cx1 = srcPos.x + dx * 0.25;
              const cy1 = srcPos.y + dy * 0.1 - 20;
              const cx2 = srcPos.x + dx * 0.75;
              const cy2 = tgtPos.y - dy * 0.1 - 20;

              const markerId =
                edge.status === 'SUPPORTED'
                  ? 'url(#arrow-emerald)'
                  : edge.status === 'WEAK'
                  ? 'url(#arrow-amber)'
                  : 'url(#arrow-rose)';

              return (
                <g key={edge.id}>
                  <path
                    d={`M ${srcPos.x} ${srcPos.y} C ${cx1} ${cy1}, ${cx2} ${cy2}, ${tgtPos.x} ${tgtPos.y}`}
                    fill="none"
                    stroke={strokeColor}
                    strokeWidth={strokeWidth}
                    strokeDasharray={edge.type === 'cross_station_link' ? 'none' : '4 3'}
                    opacity={opacity}
                    markerEnd={markerId}
                    style={{ transition: 'all 0.2s ease' }}
                  />
                  {/* Confidence pill on edge mid-point */}
                  {edge.type === 'cross_station_link' && (
                    <g transform={`translate(${(srcPos.x + tgtPos.x) / 2}, ${(srcPos.y + tgtPos.y) / 2 - 10})`}>
                      <rect
                        x="-20"
                        y="-9"
                        width="40"
                        height="18"
                        rx="4"
                        fill="rgba(15, 23, 42, 0.9)"
                        stroke={strokeColor}
                        strokeWidth="1"
                      />
                      <text
                        x="0"
                        y="3"
                        fill={strokeColor}
                        fontSize="9"
                        fontWeight="700"
                        textAnchor="middle"
                      >
                        {Math.round(edge.confidence * 100)}%
                      </text>
                    </g>
                  )}
                </g>
              );
            })}

            {/* Render Nodes */}
            {filteredNodes.map((node) => {
              const pos = nodePositions.get(node.id);
              if (!pos) return null;

              const isSelected = selectedNodeId === node.id;
              const isHovered = hoveredNodeId === node.id;
              const isConnected = highlightedEdgeIds.size > 0 && Array.from(highlightedEdgeIds).some((eid) => {
                const ed = filteredEdges.find((e) => e.id === eid);
                return ed && (ed.source === node.id || ed.target === node.id);
              });
              const isDimmed = (selectedNodeId || hoveredNodeId) && !isSelected && !isHovered && !isConnected;

              const cfg = getNodeColor(node.type);

              return (
                <g
                  key={node.id}
                  transform={`translate(${pos.x}, ${pos.y})`}
                  style={{ cursor: 'pointer', transition: 'all 0.2s ease' }}
                  opacity={isDimmed ? 0.3 : 1}
                  onMouseEnter={() => setHoveredNodeId(node.id)}
                  onMouseLeave={() => setHoveredNodeId(null)}
                  onClick={() => {
                    setSelectedNodeId(node.id);
                    if (node.type === 'incident' && onSelectIncident) {
                      onSelectIncident(node.id);
                    }
                  }}
                >
                  {/* Selection Glow Pulse Ring */}
                  {isSelected && (
                    <circle
                      r="28"
                      fill="none"
                      stroke={cfg.border}
                      strokeWidth="2.5"
                      strokeDasharray="4 2"
                      opacity="0.8"
                    />
                  )}

                  {/* Main Node Shape */}
                  {node.type === 'incident' ? (
                    <rect
                      x="-22"
                      y="-22"
                      width="44"
                      height="44"
                      rx="8"
                      fill={cfg.fill}
                      stroke={isSelected ? '#fff' : cfg.border}
                      strokeWidth={isSelected ? 2.5 : 1.5}
                      filter={isSelected ? 'drop-shadow(0 0 10px rgba(99, 102, 241, 0.6))' : 'none'}
                    />
                  ) : node.type === 'suspect' ? (
                    <circle
                      r="20"
                      fill={cfg.fill}
                      stroke={isSelected ? '#fff' : cfg.border}
                      strokeWidth={isSelected ? 2.5 : 1.5}
                      filter={isSelected ? 'drop-shadow(0 0 10px rgba(244, 63, 94, 0.6))' : 'none'}
                    />
                  ) : node.type === 'vehicle' ? (
                    <rect
                      x="-24"
                      y="-16"
                      width="48"
                      height="32"
                      rx="16"
                      fill={cfg.fill}
                      stroke={isSelected ? '#fff' : cfg.border}
                      strokeWidth={isSelected ? 2.5 : 1.5}
                      filter={isSelected ? 'drop-shadow(0 0 10px rgba(6, 182, 212, 0.6))' : 'none'}
                    />
                  ) : (
                    <polygon
                      points="0,-18 18,0 0,18 -18,0"
                      fill={cfg.fill}
                      stroke={isSelected ? '#fff' : cfg.border}
                      strokeWidth={isSelected ? 2.5 : 1.5}
                    />
                  )}

                  {/* Node Label Text */}
                  <text
                    x="0"
                    y={node.type === 'evidence' ? 28 : 32}
                    fill={isSelected ? '#fff' : '#cbd5e1'}
                    fontSize="10"
                    fontWeight="700"
                    textAnchor="middle"
                  >
                    {node.label.length > 18 ? `${node.label.slice(0, 16)}…` : node.label}
                  </text>

                  {/* Station / Subtitle Badge */}
                  <text
                    x="0"
                    y={node.type === 'evidence' ? 38 : 42}
                    fill={cfg.border}
                    fontSize="8"
                    fontWeight="600"
                    textAnchor="middle"
                  >
                    {node.station || node.type.toUpperCase()}
                  </text>
                </g>
              );
            })}
          </svg>

          {/* Legend Overlay */}
          <div
            style={{
              position: 'absolute',
              bottom: '10px',
              left: '10px',
              background: 'rgba(15, 23, 42, 0.85)',
              border: '1px solid rgba(255, 255, 255, 0.1)',
              borderRadius: '8px',
              padding: '6px 12px',
              display: 'flex',
              gap: '12px',
              fontSize: '0.65rem',
              color: '#94a3b8',
              zIndex: 2,
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
              <span style={{ width: '8px', height: '8px', borderRadius: '2px', background: '#6366f1' }} /> Incident
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
              <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#f43f5e' }} /> Suspect
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
              <span style={{ width: '12px', height: '6px', borderRadius: '4px', background: '#06b6d4' }} /> Vehicle
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
              <span style={{ width: '8px', height: '8px', transform: 'rotate(45deg)', background: '#10b981' }} /> Evidence
            </div>
            <div style={{ borderLeft: '1px solid rgba(255,255,255,0.2)', paddingLeft: '8px', display: 'flex', gap: '8px' }}>
              <span style={{ color: '#10b981' }}>― Supported</span>
              <span style={{ color: '#f59e0b' }}>― Weak</span>
              <span style={{ color: '#f43f5e' }}>― Unsupported</span>
            </div>
          </div>
        </div>

        {/* ── Inspection Panel for Selected Node ────────────────────────────── */}
        {activeSelectedNode && (
          <div
            style={{
              width: '320px',
              background: 'var(--bg-elevated, #1e293b)',
              border: '1px solid rgba(99, 102, 241, 0.3)',
              borderRadius: '12px',
              padding: '1rem',
              display: 'flex',
              flexDirection: 'column',
              gap: '0.8rem',
              animation: 'fadeIn 0.2s ease',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
              <div>
                <span
                  style={{
                    fontSize: '0.65rem',
                    fontWeight: 700,
                    padding: '2px 6px',
                    borderRadius: '4px',
                    background: getNodeColor(activeSelectedNode.type).fill,
                    color: getNodeColor(activeSelectedNode.type).text,
                    border: `1px solid ${getNodeColor(activeSelectedNode.type).border}`,
                    textTransform: 'uppercase',
                  }}
                >
                  {activeSelectedNode.type} RECORD
                </span>
                <h4 style={{ fontSize: '0.95rem', fontWeight: 700, margin: '6px 0 0 0', color: '#f8fafc' }}>
                  {activeSelectedNode.label}
                </h4>
              </div>
              <button
                onClick={() => setSelectedNodeId(null)}
                style={{ background: 'transparent', border: 'none', color: '#94a3b8', cursor: 'pointer' }}
              >
                <X size={16} />
              </button>
            </div>

            <div style={{ fontSize: '0.75rem', color: '#94a3b8', display: 'flex', flexDirection: 'column', gap: '6px' }}>
              <div>Station: <strong style={{ color: '#38bdf8' }}>{activeSelectedNode.station}</strong></div>
              <div>Status: <strong style={{ color: '#10b981' }}>{activeSelectedNode.status}</strong></div>
              {activeSelectedNode.confidence !== undefined && (
                <div>Confidence Score: <strong style={{ color: '#a855f7' }}>{Math.round(activeSelectedNode.confidence * 100)}%</strong></div>
              )}
            </div>

            <div
              style={{
                fontSize: '0.75rem',
                lineHeight: '1.4',
                color: '#e2e8f0',
                background: 'rgba(0, 0, 0, 0.25)',
                padding: '8px',
                borderRadius: '6px',
                border: '1px solid rgba(255, 255, 255, 0.05)',
              }}
            >
              {activeSelectedNode.description}
            </div>

            {/* Grounded Citations & Evidence Identifiers */}
            {(() => {
              const citations: string[] = [];
              if (activeSelectedNode.metadata) {
                if (Array.isArray(activeSelectedNode.metadata.citations)) {
                  citations.push(...activeSelectedNode.metadata.citations);
                }
                if (Array.isArray(activeSelectedNode.metadata.source_reference_ids)) {
                  citations.push(...activeSelectedNode.metadata.source_reference_ids);
                }
                if (activeSelectedNode.metadata.cctv_report_id) {
                  citations.push(`zetaris.cctv_reports.${activeSelectedNode.metadata.cctv_report_id}`);
                }
                if (activeSelectedNode.metadata.report_id) {
                  citations.push(`zetaris.forensic_reports.${activeSelectedNode.metadata.report_id}`);
                }
                if (activeSelectedNode.metadata.statement_id) {
                  citations.push(`zetaris.witness_reports.${activeSelectedNode.metadata.statement_id}`);
                }
                if (activeSelectedNode.metadata.article_id) {
                  citations.push(`zetaris.newspaper_reports.${activeSelectedNode.metadata.article_id}`);
                }
              }
              // Also collect supporting evidence IDs from connected edges
              filteredEdges
                .filter((e) => e.source === activeSelectedNode.id || e.target === activeSelectedNode.id)
                .forEach((e) => {
                  if (e.supporting_evidence_ids) {
                    e.supporting_evidence_ids.forEach((sid) => {
                      if (!citations.includes(sid)) citations.push(sid);
                    });
                  }
                });

              if (citations.length === 0 && activeSelectedNode.type === 'incident') {
                citations.push(`zetaris.police_incidents.${activeSelectedNode.id}`);
              }

              return citations.length > 0 ? (
                <div style={{ borderTop: '1px solid rgba(255,255,255,0.1)', paddingTop: '0.6rem' }}>
                  <div style={{ fontSize: '0.7rem', fontWeight: 700, color: '#10b981', marginBottom: '6px' }}>
                    GROUNDED CITATIONS & EVIDENCE ({citations.length})
                  </div>
                  <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap' }}>
                    {citations.map((c, i) => (
                      <span
                        key={i}
                        style={{
                          fontSize: '0.65rem',
                          padding: '2px 6px',
                          borderRadius: '4px',
                          background: 'rgba(16, 185, 129, 0.15)',
                          color: '#34d399',
                          border: '1px solid rgba(16, 185, 129, 0.3)',
                          fontFamily: 'monospace',
                        }}
                      >
                        {c}
                      </span>
                    ))}
                  </div>
                </div>
              ) : null;
            })()}

            {/* Entity Properties & Telemetry */}
            {activeSelectedNode.metadata && Object.keys(activeSelectedNode.metadata).length > 0 && (
              <div style={{ borderTop: '1px solid rgba(255,255,255,0.1)', paddingTop: '0.6rem' }}>
                <div style={{ fontSize: '0.7rem', fontWeight: 700, color: '#94a3b8', marginBottom: '6px' }}>
                  ENTITY PROPERTIES & TELEMETRY
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: '4px', fontSize: '0.7rem', maxHeight: '110px', overflowY: 'auto' }}>
                  {Object.entries(activeSelectedNode.metadata)
                    .filter(([, v]) => typeof v === 'string' || typeof v === 'number' || typeof v === 'boolean')
                    .slice(0, 8)
                    .map(([k, v]) => (
                      <div key={k} style={{ display: 'flex', justifyContent: 'space-between', background: 'rgba(255, 255, 255, 0.03)', padding: '2px 6px', borderRadius: '3px' }}>
                        <span style={{ color: '#64748b' }}>{k.replace(/_/g, ' ')}:</span>
                        <span style={{ color: '#cbd5e1', fontWeight: 600 }}>{String(v)}</span>
                      </div>
                    ))}
                </div>
              </div>
            )}

            {/* Connected Links Summary */}
            <div style={{ borderTop: '1px solid rgba(255,255,255,0.1)', paddingTop: '0.6rem' }}>
              <div style={{ fontSize: '0.7rem', fontWeight: 700, color: '#94a3b8', marginBottom: '6px' }}>
                DIRECT CONNECTIONS ({filteredEdges.filter((e) => e.source === activeSelectedNode.id || e.target === activeSelectedNode.id).length})
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', maxHeight: '140px', overflowY: 'auto' }}>
                {filteredEdges
                  .filter((e) => e.source === activeSelectedNode.id || e.target === activeSelectedNode.id)
                  .map((e) => {
                    const peerId = e.source === activeSelectedNode.id ? e.target : e.source;
                    const peer = nodes.find((n) => n.id === peerId);
                    return (
                      <div
                        key={e.id}
                        onClick={() => setSelectedNodeId(peerId)}
                        style={{
                          fontSize: '0.7rem',
                          padding: '4px 8px',
                          borderRadius: '4px',
                          background: 'rgba(255, 255, 255, 0.04)',
                          display: 'flex',
                          justifyContent: 'space-between',
                          alignItems: 'center',
                          cursor: 'pointer',
                        }}
                      >
                        <span style={{ color: '#cbd5e1' }}>{peer?.label || peerId}</span>
                        <span style={{ color: getEdgeStroke(e), fontWeight: 700 }}>
                          {Math.round(e.confidence * 100)}%
                        </span>
                      </div>
                    );
                  })}
              </div>
            </div>

            {activeSelectedNode.type === 'incident' && onSelectIncident && (
              <button
                onClick={() => onSelectIncident(activeSelectedNode.id)}
                style={{
                  marginTop: 'auto',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '6px',
                  padding: '6px 12px',
                  borderRadius: '6px',
                  background: 'linear-gradient(135deg, #6366f1, #0ea5e9)',
                  color: '#fff',
                  border: 'none',
                  fontSize: '0.75rem',
                  fontWeight: 600,
                  cursor: 'pointer',
                }}
              >
                <ExternalLink size={13} /> View Full Incident Dossier
              </button>
            )}
          </div>
        )}
      </div>

      {/* ── Active Correlated Leads Ribbon ───────────────────────────────────── */}
      <div
        style={{
          background: 'rgba(15, 23, 42, 0.85)',
          border: '1px solid rgba(99, 102, 241, 0.3)',
          borderRadius: '8px',
          padding: '0.75rem',
        }}
      >
        <div style={{ fontSize: '0.75rem', fontWeight: 600, color: '#94a3b8', marginBottom: '0.4rem' }}>
          CONNECTIONS IN THIS RESULT ({filteredEdges.length}); percentages are the Finder's uncalibrated heuristic, shown only on links:
        </div>
        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
          {filteredEdges.map((e) => (
            <span
              key={e.id}
              onClick={() => setSelectedNodeId(e.source)}
              style={{
                fontSize: '0.7rem',
                padding: '3px 8px',
                borderRadius: '6px',
                background: 'rgba(99, 102, 241, 0.15)',
                border: `1px solid ${getEdgeStroke(e)}`,
                color: '#e0e7ff',
                display: 'inline-flex',
                alignItems: 'center',
                gap: '6px',
                cursor: 'pointer',
              }}
            >
              <strong>{e.source}</strong> ↔ <strong>{e.target}</strong>
              <span style={{ color: getEdgeStroke(e), fontWeight: 700 }}>
                {e.confidence > 0 ? `(${Math.round(e.confidence * 100)}%)` : ''}
              </span>
            </span>
          ))}
          {filteredEdges.length === 0 && (
            <span style={{ fontSize: '0.75rem', color: '#64748b' }}>
              No correlation pathways match the current precinct, entity, or confidence filters.
            </span>
          )}
        </div>
      </div>
    </div>
  );
};
