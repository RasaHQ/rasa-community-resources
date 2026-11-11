import React, { useEffect } from 'react';
import { useI18n } from '../../i18n/LanguageContext';

export function ContactSection() {
  const { t } = useI18n();

  useEffect(() => {
    const el = document.querySelector('.contact-section');
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

  const cards = [
    { icon: '✉️', label: t('contact.email'), value: 'hello@terraenergy.com' },
    { icon: '📞', label: t('contact.phone'), value: '+33 6 12 34 56 78' },
    { icon: '📍', label: t('contact.location'), value: 'Lyon, France' },
  ];

  return (
    <section id="contact" className="contact-section">
      <div className="contact-inner">
        <span className="section-label">{t('contact.label')}</span>
        <h2 className="contact-title">{t('contact.title')}</h2>
        <p className="contact-sub">{t('contact.sub')}</p>
        <div className="contact-cards">
          {cards.map((c, i) => (
            <div className="contact-card" key={i}>
              <div className="contact-card-icon">{c.icon}</div>
              <h4>{c.label}</h4>
              <p>{c.value}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

export default ContactSection;