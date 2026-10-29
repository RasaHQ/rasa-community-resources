import React, { createContext, useContext, useMemo, useState, useCallback } from 'react';
import { Lang, TKey, LANGS, translate, formatNumber } from './dictionaries';

const STORAGE_KEY = 'terraenergy.lang';

export interface I18nValue {
  lang: Lang;
  isChosen: boolean;
  setLang: (lang: Lang) => void;
  t: (key: TKey, params?: Record<string, string | number>) => string;
  fmt: (value: number) => string;
}

const I18nContext = createContext<I18nValue | null>(null);

function isLang(v: string | null): v is Lang {
  return !!v && LANGS.some(l => l.code === v);
}

const DEFAULT_I18N: I18nValue = {
  lang: 'fr',
  isChosen: true,
  setLang: () => {},
  t: (key, params) => translate('fr', key, params),
  fmt: value => formatNumber('fr', value),
};

export function I18nProvider({ children }: { children: React.ReactNode }) {
  const [lang, setLangState] = useState<Lang | null>(() => {
    try {
      const saved = window.localStorage.getItem(STORAGE_KEY);
      return isLang(saved) ? saved : null;
    } catch {
      return null;
    }
  });

  const setLang = useCallback((l: Lang) => {
    try {
      window.localStorage.setItem(STORAGE_KEY, l);
    } catch {
      /* ignore */
    }
    setLangState(l);
  }, []);

  const value = useMemo<I18nValue>(() => {
    const effective: Lang = lang ?? 'fr';
    return {
      lang: effective,
      isChosen: lang !== null,
      setLang,
      t: (key, params) => translate(effective, key, params),
      fmt: n => formatNumber(effective, n),
    };
  }, [lang, setLang]);

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18nValue {
  return useContext(I18nContext) ?? DEFAULT_I18N;
}
