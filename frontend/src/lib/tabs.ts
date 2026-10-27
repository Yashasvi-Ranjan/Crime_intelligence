export type Tab = 'overview' | 'investigation' | 'incidents' | 'sources' | 'zetaris';

export const TABS: { id: Tab; label: string; cmd: string }[] = [
  { id: 'overview', label: 'overview', cmd: 'xsci overview' },
  { id: 'investigation', label: 'investigate', cmd: 'xsci investigate' },
  { id: 'incidents', label: 'incidents', cmd: 'xsci incidents --all' },
  { id: 'sources', label: 'sources', cmd: 'xsci sources ls' },
  { id: 'zetaris', label: 'data-layer', cmd: 'xsci zetaris status' },
];
