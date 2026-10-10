import React, { useEffect, useRef, useState } from 'react';
import { LANGS } from './dictionaries';
import { useI18n } from './LanguageContext';

export default function LanguageSwitcher() {
  const { lang, setLang } = useI18n();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', onClick);
    return () => document.removeEventListener('mousedown', onClick);
  }, [open]);

  const current = LANGS.find(l => l.code === lang) ?? LANGS[0];

  return (
    <div className="lang-switcher" ref={ref}>
      <button
        className={`lang-switcher-btn${open ? ' open' : ''}`}
        onClick={() => setOpen(o => !o)}
        aria-label="Change language"
      >
        <svg className="globe" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6">
          <circle cx="12" cy="12" r="9" />
          <path d="M3 12h18M12 3a15 15 0 0 1 0 18 15 15 0 0 1 0-18z" />
        </svg>
        <span className="lang-code">{current.code.toUpperCase()}</span>
        <span className="lang-native">{current.native}</span>
        <svg className="chevron" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <polyline points="6 9 12 15 18 9" />
        </svg>
      </button>

      {open && (
        <div className="lang-switcher-menu" role="menu">
          {LANGS.map(l => (
            <button
              key={l.code}
              role="menuitem"
              className={`lang-switcher-item${l.code === lang ? ' active' : ''}`}
              onClick={() => {
                setLang(l.code);
                setOpen(false);
              }}
            >
              <span className="lang-code">{l.code.toUpperCase()}</span>
              <span className="lang-native">{l.native}</span>
              <svg className="check" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                <polyline points="20 6 9 17 4 12" />
              </svg>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}