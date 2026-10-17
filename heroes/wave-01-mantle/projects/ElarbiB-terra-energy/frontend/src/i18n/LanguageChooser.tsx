import React, { useState, useEffect } from 'react';
import { LANGS } from './dictionaries';
import { useI18n } from './LanguageContext';

export default function LanguageChooser() {
  const { setLang, t } = useI18n();
  const [index, setIndex] = useState(0);

  useEffect(() => {
    const id = setInterval(() => setIndex(i => (i + 1) % LANGS.length), 5000);
    return () => clearInterval(id);
  }, []);

  const current = LANGS[index];

  return (
    <div className="lang-chooser">
      <video autoPlay muted loop playsInline preload="metadata" className="lang-chooser-video">
        <source src="/project.mp4" type="video/mp4" />
      </video>
      <div className="lang-chooser-overlay" />

      <div className="lang-chooser-content">
        <div className="lang-chooser-brand">
          <img src="/lvwre.png" alt="LvWRE" />
          <div className="lang-chooser-name">
            Terra<span style={{ color: '#f5a623' }}>Energy</span>
          </div>
          <div className="lang-chooser-tagline">Intelligent Renewable Energy Platform</div>
        </div>

        <h2 className="lang-chooser-title" key={current.code}>
          {current.native}
        </h2>

        <div className="lang-cards">
          {LANGS.map(l => (
            <button
              key={l.code}
              className="lang-card"
              onClick={() => setLang(l.code)}
            >
              <span className="lang-flag">{l.code === 'fr' ? '🇫🇷' : l.code === 'en' ? '🇬🇧' : l.code === 'de' ? '🇩🇪' : '🇪🇸'}</span>
              <span className="lang-native">{l.native}</span>
              <span className="lang-enter">{t('lang.enter')} →</span>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
