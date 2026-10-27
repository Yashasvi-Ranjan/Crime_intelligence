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
// If the live backend (tunnelled to the developer's machine) is unreachable, requests are retried against /offline-api: the same API served in
// offline sample mode (bundled synthetic data, recorded Nemotron responses). The UI shows a banner whenever this is active.
const OFFLINE_BASE = '/offline-api';
const OFFLINE_HOLD_MS = 30_000;
let offlineUntil = 0;
const offlineListeners = new Set<(offline: boolean) => void>();

export function onOfflineChange(cb: (offline: boolean) => void): () => void {
  offlineListeners.add(cb);
  cb(Date.now() < offlineUntil);
  return () => offlineListeners.delete(cb);
}

function setOffline(offline: boolean): void {
  const was = Date.now() < offlineUntil;
  offlineUntil = offline ? Date.now() + OFFLINE_HOLD_MS : 0;
  if (was !== offline) offlineListeners.forEach((cb) => cb(offline));
}

// A tunnel/proxy failure, not an application error: no response, a Cloudflare 52x, or any 5xx without a JSON body (the backend's own errors are JSON).
function backendDown(res: Response | null): boolean {
  if (!res) return true;
  if (res.status >= 520) return true;
  return res.status >= 500 && !(res.headers.get('content-type') || '').includes('json');
}

async function apiFetch(url: string, init?: RequestInit): Promise<Response> {
  if (Date.now() >= offlineUntil) {
    let res: Response | null = null;
    try {
      const isGet = !init || !init.method || init.method === 'GET';
      res = await fetch(url, isGet ? { ...init, signal: AbortSignal.timeout(15_000) } : init);
    } catch {
      res = null;
    }
    if (!backendDown(res)) {
      setOffline(false);
      return res as Response;
    }
    setOffline(true);
  }
  return fetch(url.replace(/^\/api/, OFFLINE_BASE), init);
}

async function fetchJson<T>(url: string): Promise<T> {
  const res = await apiFetch(url);
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

  // ── Investigations & Agents ──────────────────────────────────────────────
  analyzeInvestigation: (req: import('../types').InvestigationRequest): Promise<import('../types').InvestigationResponse> =>
    postJson<import('../types').InvestigationResponse>(`${API_BASE}/investigations/analyze`, req),

  getSampleScenarios: (): Promise<import('../types').SampleScenarioMeta[]> =>
    fetchJson<import('../types').SampleScenarioMeta[]>(`${API_BASE}/investigations/samples`),

  getAIDiagnostic: (): Promise<import('../types').AIDiagnosticResponse> =>
    fetchJson<import('../types').AIDiagnosticResponse>(`${API_BASE}/ai/diagnostic`),

  getEngineHealth: (): Promise<import('../types').EngineHealthResponse> =>
    fetchJson<import('../types').EngineHealthResponse>(`${API_BASE}/engine/health`),
};

async function postJson<T>(url: string, data: any): Promise<T> {
  const res = await apiFetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(data),
  });
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
