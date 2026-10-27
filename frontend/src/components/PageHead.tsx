import React from 'react';

/** `$ command` line that opens each page, with the page's own meta on the right. */
export const PageHead: React.FC<{ cmd: string; meta?: React.ReactNode }> = ({ cmd, meta }) => (
  <div className="page-head">
    <div className="prompt"><i>$</i>{cmd}<span className="cursor" aria-hidden /></div>
    {meta && <div className="meta">{meta}</div>}
  </div>
);
