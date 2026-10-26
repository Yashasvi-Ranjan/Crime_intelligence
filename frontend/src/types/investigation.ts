/**
 * AEGIS Crime Intelligence - Investigation Types
 * Milestone 3: Knowledge Graph, Execution Trace, and Evidence Pinboard
 */

export * from './index';

export interface TraceEvent {
  timestamp: string;
  phase: string;
  agent: string;
  model: string;
  receipt_id: string;
  details?: Record<string, any>;
}

export interface InvestigationTraceResponse {
  run_id: string;
  events: TraceEvent[];
  total_events: number;
}

export type EntityType = 'incident' | 'suspect' | 'vehicle' | 'evidence';

export interface GraphEntityNode {
  id: string;
  type: EntityType;
  label: string;
  station?: string;
  crimeType?: string;
  description?: string;
  status?: string;
  confidence?: number;
  metadata?: Record<string, any>;
  x?: number;
  y?: number;
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  type?: 'cross_station_link' | 'involves_suspect' | 'involves_vehicle' | 'supported_by_evidence';
  confidence: number;
  status: 'SUPPORTED' | 'WEAK' | 'UNSUPPORTED';
  basis?: string;
  supporting_evidence_ids?: string[];
}

export interface EvidenceCardItem {
  id: string;
  type: 'cctv' | 'witness' | 'forensic' | 'newspaper' | 'incident';
  title: string;
  station: string;
  timestamp?: string;
  location?: string;
  summary: string;
  corroboratesIncidentIds: string[];
  groundingStatus: 'GROUNDED' | 'UNVERIFIED';
  citations: string[];
  metadata: Record<string, any>;
  pinned?: boolean;
}
