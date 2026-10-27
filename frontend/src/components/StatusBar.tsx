import React, { useEffect, useState } from 'react';
import { onOfflineChange } from '../services/api';
import { ZetarisHealthResponse } from '../types';
import { Tab } from '../lib/tabs';

interface Props {
  tab: Tab;
  zetarisHealth: ZetarisHealthResponse | null;
}

const pad = (n: number) => String(n).padStart(2, '0');

/** vim-style bottom bar: mode, route, backend, clock. */
export const StatusBar: React.FC<Props> = ({ tab, zetarisHealth }) => {
  const [offline, setOffline] = useState(false);
  const [now, setNow] = useState(new Date());
  useEffect(() => onOfflineChange(setOffline), []);
  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(id);
  }, []);

  const live = zetarisHealth?.status === 'connected';
  return (
    <footer className="status-bar" role="contentinfo">
      <span className={`sb-mode ${offline ? 'warn' : ''}`}>{offline ? 'OFFLINE DEMO' : 'LIVE'}</span>
      <span>~/<b>{tab}</b></span>
      <span className="sb-hide">data: <b>{live ? 'zetaris' : 'local fallback'}</b></span>
      <span className="sb-hide">synthetic data only</span>
      <span className="sb-grow" />
      <span className="sb-hide">1-5 switch · ⌘K palette · esc close</span>
      <span>
        {now.getUTCFullYear()}-{pad(now.getUTCMonth() + 1)}-{pad(now.getUTCDate())} {pad(now.getUTCHours())}:{pad(now.getUTCMinutes())}:{pad(now.getUTCSeconds())}Z
      </span>
    </footer>
  );
};
