import type { InvestigationResponse } from '../types';

export interface EvidenceQuote {
  id: string;
  kind: string;
  quote: string | null;
}

const ID_KEYS = ['evidence_report_id', 'cctv_report_id', 'witness_report_id', 'news_id', 'incident_id'];
const TEXT_KEYS = ['result_summary', 'movement_description', 'observation_text', 'headline', 'description', 'method_description', 'summary'];
const KINDS: Array<[keyof InvestigationResponse['supporting_evidence'], string]> = [
  ['forensic_reports', 'forensic'], ['cctv_reports', 'CCTV'], ['witness_reports', 'witness'], ['newspaper_reports', 'news'],
];

/** Index of the records actually returned in the response, keyed by record id, so citations can show the cited text. */
export function buildEvidenceIndex(result: Pick<InvestigationResponse, 'supporting_evidence' | 'candidate_incidents'>): Map<string, EvidenceQuote> {
  const idx = new Map<string, EvidenceQuote>();
  const add = (rec: Record<string, any>, kind: string) => {
    const idKey = ID_KEYS.find((k) => rec[k]);
    if (!idKey) return;
    const textKey = TEXT_KEYS.find((k) => typeof rec[k] === 'string' && rec[k].trim());
    idx.set(String(rec[idKey]), { id: String(rec[idKey]), kind, quote: textKey ? String(rec[textKey]) : null });
  };
  for (const [key, kind] of KINDS) (result.supporting_evidence?.[key] ?? []).forEach((r) => add(r, kind));
  (result.candidate_incidents ?? []).forEach((r) => add(r, 'incident'));
  return idx;
}
