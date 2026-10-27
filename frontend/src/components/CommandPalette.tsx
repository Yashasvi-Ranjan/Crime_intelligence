import React, { useEffect, useMemo, useRef, useState } from 'react';
import { TABS } from '../lib/tabs';

export interface Command {
  id: string;
  label: string;
  hint?: string;
  run: () => void;
}

interface Props {
  open: boolean;
  onClose: () => void;
  commands: Command[];
}

export const CommandPalette: React.FC<Props> = ({ open, onClose, commands }) => {
  const [q, setQ] = useState('');
  const [sel, setSel] = useState(0);
  const input = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (open) {
      setQ('');
      setSel(0);
      setTimeout(() => input.current?.focus(), 0);
    }
  }, [open]);

  const items = useMemo(() => {
    const needle = q.trim().toLowerCase();
    return needle ? commands.filter((c) => (c.label + ' ' + (c.hint ?? '')).toLowerCase().includes(needle)) : commands;
  }, [q, commands]);

  if (!open) return null;

  const exec = (c?: Command) => {
    if (!c) return;
    onClose();
    c.run();
  };

  return (
    <div className="cmdk-backdrop" onMouseDown={onClose}>
      <div className="cmdk" role="dialog" aria-label="Command palette" onMouseDown={(e) => e.stopPropagation()}>
        <div className="cmdk-input">
          <span>$</span>
          <input
            ref={input}
            value={q}
            placeholder="jump to a page or filter by station…"
            onChange={(e) => { setQ(e.target.value); setSel(0); }}
            onKeyDown={(e) => {
              if (e.key === 'ArrowDown') { e.preventDefault(); setSel((s) => Math.min(s + 1, items.length - 1)); }
              else if (e.key === 'ArrowUp') { e.preventDefault(); setSel((s) => Math.max(s - 1, 0)); }
              else if (e.key === 'Enter') exec(items[sel]);
              else if (e.key === 'Escape') onClose();
            }}
          />
        </div>
        <div className="cmdk-list">
          {items.length === 0 && <div className="cmdk-item" style={{ cursor: 'default' }}>no matches</div>}
          {items.map((c, i) => (
            <button key={c.id} className={`cmdk-item ${i === sel ? 'sel' : ''}`} onMouseEnter={() => setSel(i)} onClick={() => exec(c)}>
              <span>{i === sel ? '> ' : '  '}{c.label}</span>
              {c.hint && <small>{c.hint}</small>}
            </button>
          ))}
        </div>
        <div className="cmdk-foot"><span>↑↓ navigate</span><span>↵ run</span><span>esc close</span></div>
      </div>
    </div>
  );
};

export const tabCommands = (go: (id: (typeof TABS)[number]['id']) => void): Command[] =>
  TABS.map((t, i) => ({ id: t.id, label: t.cmd, hint: `go · ${i + 1}`, run: () => go(t.id) }));
