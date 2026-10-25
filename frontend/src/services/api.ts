import {
  AppHealthResponse,
  DashboardSummary,
  IncidentEvidenceResponse,
  IncidentFilters,
  IncidentListResponse,
  PoliceIncident,
  SourceListResponse,
  SourceRecordsResponse,
  ZetarisHealthResponse,
} from '../types';

const API_BASE = '/api';

async function fetchJson<T>(url: string): Promise<T> {
  const res = await fetch(url);
  if (!res.ok) {
    let errorMsg = `Request failed: ${res.status} ${res.statusText}`;
    try {
      const err = await res.json();
      if (err.detail) errorMsg = err.detail;
    } catch {
      // ignore
    }
    throw new Error(errorMsg);
  }
  return res.json() as Promise<T>;
}

export const api = {
  getAppHealth: (): Promise<AppHealthResponse> =>
    fetchJson<AppHealthResponse>(`${API_BASE}/health`),

  getZetarisHealth: (): Promise<ZetarisHealthResponse> =>
    fetchJson<ZetarisHealthResponse>(`${API_BASE}/health/zetaris`),

  getDashboardSummary: (): Promise<DashboardSummary> =>
    fetchJson<DashboardSummary>(`${API_BASE}/dashboard/summary`),

  getIncidents: (filters: IncidentFilters): Promise<IncidentListResponse> => {
    const params = new URLSearchParams();
    params.set('page', String(filters.page || 1));
    params.set('page_size', String(filters.pageSize || 50));
    if (filters.search) params.set('search', filters.search);
    if (filters.station && filters.station !== 'ALL') params.set('station', filters.station);
    if (filters.crimeType && filters.crimeType !== 'ALL') params.set('crime_type', filters.crimeType);
    if (filters.status && filters.status !== 'ALL') params.set('status', filters.status);
    if (filters.dateFrom) params.set('date_from', filters.dateFrom);
    if (filters.dateTo) params.set('date_to', filters.dateTo);
    if (filters.sortBy) params.set('sort_by', filters.sortBy);
    if (typeof filters.sortDesc === 'boolean') params.set('sort_desc', String(filters.sortDesc));

    return fetchJson<IncidentListResponse>(`${API_BASE}/incidents?${params.toString()}`);
  },

  getIncidentById: (incidentId: string): Promise<PoliceIncident> =>
    fetchJson<PoliceIncident>(`${API_BASE}/incidents/${encodeURIComponent(incidentId)}`),

  getIncidentEvidence: (incidentId: string): Promise<IncidentEvidenceResponse> =>
    fetchJson<IncidentEvidenceResponse>(`${API_BASE}/incidents/${encodeURIComponent(incidentId)}/evidence`),

  getSources: (): Promise<SourceListResponse> =>
    fetchJson<SourceListResponse>(`${API_BASE}/sources`),

  getSourceRecords: (
    source: string,
    page: number = 1,
    pageSize: number = 25,
    search?: string
  ): Promise<SourceRecordsResponse> => {
    const params = new URLSearchParams({
      page: String(page),
      page_size: String(pageSize),
    });
    if (search) params.set('search', search);
    return fetchJson<SourceRecordsResponse>(`${API_BASE}/sources/${encodeURIComponent(source)}/records?${params.toString()}`);
  },

  getSourceRecordById: (
    source: string,
    recordId: string
  ): Promise<{ source: string; record: Record<string, any>; data_mode: string }> =>
    fetchJson<{ source: string; record: Record<string, any>; data_mode: string }>(
      `${API_BASE}/sources/${encodeURIComponent(source)}/records/${encodeURIComponent(recordId)}`
    ),
};
