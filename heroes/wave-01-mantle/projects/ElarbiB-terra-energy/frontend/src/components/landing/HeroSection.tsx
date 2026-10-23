import React, { useEffect, useRef } from 'react';
import { useI18n } from '../../i18n/LanguageContext';

export function HeroSection() {
  const { t } = useI18n();
  const videoRef = useRef<HTMLVideoElement>(null);

  useEffect(() => {
    const id = window.setTimeout(() => {
      videoRef.current?.play().catch(() => {});
    }, 600);
    return () => window.clearTimeout(id);
  }, []);

  return (
    <section className="hero" id="hero">
      <video ref={videoRef} muted loop playsInline preload="metadata" className="hero-video">
        <source src="/project.mp4" type="video/mp4" />
      </video>
      <div className="hero-gradient" />
      <div className="hero-content">
        <h1 className="hero-title">
          {t('hero.title1')}<br />
          <span className="hero-highlight">{t('hero.title2')}</span><br />
          {t('hero.title3')}
        </h1>
        <p className="hero-sub">
          {t('hero.sub')}
        </p>
      </div>
    </section>
  );
}

export default HeroSection;