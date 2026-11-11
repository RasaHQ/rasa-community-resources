import React, { useEffect } from 'react';
import { useI18n } from '../../i18n/LanguageContext';
import { TKey } from '../../i18n/dictionaries';

interface FeatureDef {
  image: string;
  titleKey: TKey;
  textKey: TKey;
}

const FEATURES: FeatureDef[] = [
  { image: '/feature-1.jpeg', titleKey: 'feature1.title', textKey: 'feature1.text' },
  { image: '/feature-2.jpeg', titleKey: 'feature2.title', textKey: 'feature2.text' },
  { image: '/feature-3.jpeg', titleKey: 'feature3.title', textKey: 'feature3.text' },
  { image: '/feature-4.jpeg', titleKey: 'feature4.title', textKey: 'feature4.text' },
];

export function FeatureSection() {
  const { t } = useI18n();

  useEffect(() => {
    const rows = Array.from(document.querySelectorAll('.feature-row'));
    const observer = new IntersectionObserver(
      entries =>
        entries.forEach(e => {
          if (e.isIntersecting) e.target.classList.add('visible');
        }),
      { threshold: 0.2 }
    );
    rows.forEach(r => observer.observe(r));
    return () => observer.disconnect();
  }, []);

  return (
    <section id="features" className="features-section">
      <div className="features-header">
        <span className="section-label">{t('features.label')}</span>
        <h2 className="features-title">
          {t('features.title1')}<br />
          {t('features.title2')}
        </h2>
      </div>
      <div className="features-list">
        {FEATURES.map((f, i) => (
          <div key={i} className={`feature-row${i % 2 === 1 ? ' right' : ''}`}>
            <div className="feature-image-wrap">
              <img className="feature-image" src={f.image} alt={t(f.titleKey)} loading="lazy" />
            </div>
            <div className="feature-text">
              <span className="feature-number">0{i + 1}</span>
              <h3 className="feature-title">{t(f.titleKey)}</h3>
              <p className="feature-para">{t(f.textKey)}</p>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

export default FeatureSection;