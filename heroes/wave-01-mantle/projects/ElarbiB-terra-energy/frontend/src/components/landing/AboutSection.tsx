import React, { useEffect } from 'react';
import { useI18n } from '../../i18n/LanguageContext';
import { TKey } from '../../i18n/dictionaries';

const ABOUT_CARDS: { base: string; image: string }[] = [
  { base: 'about.card1', image: '/icon-nasa.jpg' },
  { base: 'about.card2', image: '/icon-ia.jpg' },
  { base: 'about.card3', image: '/icon-viz.jpg' },
  { base: 'about.card4', image: '/icon-earth.jpg' },
];

export function AboutSection() {
  const { t } = useI18n();

  useEffect(() => {
    const el = document.querySelector('.about-section');
    if (!el) return;
    const observer = new IntersectionObserver(
      entries =>
        entries.forEach(e => {
          if (e.isIntersecting) e.target.classList.add('visible');
        }),
      { threshold: 0.15 }
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  return (
    <section id="about" className="about-section">
      <div className="about-inner">
        <span className="section-label">{t('about.label')}</span>
        <h2 className="about-title">
          {t('about.title1')}<br />
          {t('about.title2')}
        </h2>
        <div className="about-grid">
          {ABOUT_CARDS.map(card => (
            <div className="about-card" key={card.base}>
              <img className="about-card-img" src={card.image} alt="" loading="lazy" />
              <h3>{t(`${card.base}.title` as TKey)}</h3>
              <p>{t(`${card.base}.text` as TKey)}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

export default AboutSection;