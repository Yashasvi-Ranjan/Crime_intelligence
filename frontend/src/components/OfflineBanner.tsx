import React, { useEffect, useState } from 'react';
import { onOfflineChange } from '../services/api';

/** Shown only while the live backend is unreachable and requests are being served by the offline sample mode. */
export const OfflineBanner: React.FC = () => {
  const [offline, setOffline] = useState(false);
  useEffect(() => onOfflineChange(setOffline), []);
  if (!offline) return null;
  return (
    <div role="status" className="banner warning" style={{ margin: 0, border: 0, borderBottom: '1px solid rgba(245,177,76,.35)', borderLeft: 0, justifyContent: 'center' }}>
      [WARN] Live backend unreachable: showing the OFFLINE DEMO (bundled synthetic data and recorded model responses). This is not live Zetaris or live model output.
    </div>
  );
};
