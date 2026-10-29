import React from 'react';
import { useI18n } from '../../i18n/LanguageContext';

export function Footer() {
  const { t } = useI18n();

  return (
    <footer className="footer">
      <div className="footer-inner">
        <div className="footer-brand">
          <img className="footer-logo" src="/lvwre.png" alt="TerraEnergy" />
          <span>Terra<span style={{ color: '#f5a623' }}>Energy</span></span>
        </div>
        <span className="footer-copy">
          © {new Date().getFullYear()} TerraEnergy — {t('footer.rights')}
        </span>
      </div>
    </footer>
  );
}

export default Footer;