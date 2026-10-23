import React, { useEffect, useState } from 'react';
import { useI18n } from '../../i18n/LanguageContext';
import LanguageSwitcher from '../../i18n/LanguageSwitcher';

const SECTIONS = ['hero', 'features', 'about', 'contact'];

export function Navbar() {
  const { t } = useI18n();
  const [scrolled, setScrolled] = useState(false);
  const [active, setActive] = useState('');

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 20);
    onScroll();
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  useEffect(() => {
    const observer = new IntersectionObserver(
      entries => {
        entries.forEach(e => {
          if (e.isIntersecting) setActive(e.target.id);
        });
      },
      { threshold: 0.4 }
    );
    SECTIONS.forEach(id => {
      const el = document.getElementById(id);
      if (el) observer.observe(el);
    });
    return () => observer.disconnect();
  }, []);

  const goTo = (id: string) => {
    document.getElementById(id)?.scrollIntoView({ behavior: 'smooth' });
  };

  return (
    <nav className={`navbar${scrolled ? ' scrolled' : ''}`}>
      <div className="navbar-inner">
        <button className="navbar-brand" onClick={() => goTo('hero')}>
          <img src="/lvwre.png" alt="TerraEnergy" className="navbar-logo-free" />
          <span className="navbar-brand-text">
            Terra<span className="brand-highlight">Energy</span>
          </span>
        </button>

        <div className="navbar-links">
          {(['features', 'about', 'contact'] as const).map(id => (
            <button
              key={id}
              className={active === id ? 'active' : ''}
              onClick={() => goTo(id)}
            >
              {t(`nav.${id}`)}
            </button>
          ))}
        </div>

        <LanguageSwitcher />
      </div>
    </nav>
  );
}

export default Navbar;