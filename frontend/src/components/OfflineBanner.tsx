import React, { useEffect, useState } from 'react';
import { onOfflineChange } from '../services/api';

/** Shown only while the live backend is unreachable and requests are being served by the offline sample mode. */
export const OfflineBanner: React.FC = () => {
  const [offline, setOffline] = useState(false);
  useEffect(() => onOfflineChange(setOffline), []);
  if (!offline) return null;
  return (
    <div
      role="status"
      style={{
        background: 'rgba(245, 158, 11, 0.15)',
        borderBottom: '1px solid rgba(245, 158, 11, 0.4)',
        color: '#fcd34d',
        padding: '8px 16px',
        fontSize: '0.8rem',
        textAlign: 'center',
      }}
    >
      Live backend unreachable: showing the OFFLINE DEMO (bundled synthetic data and recorded Nemotron responses). This is not live Zetaris or live model output.
    </div>
  );
};
