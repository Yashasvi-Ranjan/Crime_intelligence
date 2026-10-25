export type StationId = 'NORTH' | 'CENTRAL' | 'RIVERSIDE';

export type DataSource =
  | 'police_incidents'
  | 'newspaper_reports'
  | 'witness_reports'
  | 'cctv_reports'
  | 'forensic_reports';

export interface AppHealthResponse {
  status: string;
  version: string;
  environment: string;
}

export interface ZetarisHealthResponse {
  status: 'connected' | 'not_configured' | 'connection_failed' | 'query_failed';
  mode: 'zetaris_live' | 'local_fallback';
  configured: boolean;
  message: string;
  tables_verified?: string[];
  error_detail?: string;
}

export interface PaginationInfo {
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
  has_next: boolean;
  has_prev: boolean;
}

export interface StationCount {
  station_id: string;
  count: number;
}

export interface CrimeTypeCount {
  crime_type: string;
  count: number;
}

export interface StatusCount {
  status: string;
  count: number;
}

export interface SourceCount {
  source: string;
  count: number;
}

export interface TimelineBucket {
  period: string;
  count: number;
}

export interface DashboardSummary {
  total_incidents: number;
  by_station: StationCount[];
  by_crime_type: CrimeTypeCount[];
  by_status: StatusCount[];
  by_source: SourceCount[];
  incident_timeline: TimelineBucket[];
  data_mode: 'zetaris_live' | 'local_fallback';
}

export interface PoliceIncident {
  incident_id: string;
  station_id: StationId;
  reported_at: string | null;
  occurred_from: string | null;
  occurred_to: string | null;
  crime_type: string;
  location_id: string;
  location_description: string;
  method_description: string;
  property_involved: string[];
  estimated_loss: number | null;
  status: 'OPEN' | 'UNDER_INVESTIGATION' | 'CLOSED' | 'UNRESOLVED';
  source_reference_ids: string[];
  data_quality: string;
}

export interface IncidentListResponse {
  items: PoliceIncident[];
  pagination: PaginationInfo;
  data_mode: 'zetaris_live' | 'local_fallback';
}

export interface SourceInfo {
  name: DataSource;
  label: string;
  record_count: number;
  primary_key_field: string;
  description: string;
}

export interface SourceListResponse {
  sources: SourceInfo[];
  data_mode: 'zetaris_live' | 'local_fallback';
}

export interface SourceRecordsResponse {
  source: string;
  items: Record<string, any>[];
  pagination: PaginationInfo;
  data_mode: 'zetaris_live' | 'local_fallback';
}

export interface EvidenceLink {
  source: string;
  record_id: string;
  link_type: 'direct_reference' | 'inferred_spatial_temporal';
  link_basis: string;
  record: Record<string, any>;
}

export interface IncidentEvidenceResponse {
  incident_id: string;
  incident: PoliceIncident | null;
  direct_links: EvidenceLink[];
  inferred_links: EvidenceLink[];
  data_mode: 'zetaris_live' | 'local_fallback';
}

export interface IncidentFilters {
  page: number;
  pageSize: number;
  search?: string;
  station?: string;
  crimeType?: string;
  status?: string;
  dateFrom?: string;
  dateTo?: string;
  sortBy?: string;
  sortDesc?: boolean;
}
