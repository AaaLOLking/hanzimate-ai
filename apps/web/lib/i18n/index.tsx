"use client";

import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";

import { en } from "./en";
import { zh, type I18nKey } from "./zh";

export type { I18nKey };

export type Locale = "zh" | "en";

const STORAGE_KEY = "hanzimate-locale";

const dictionaries: Record<Locale, Record<I18nKey, string>> = { zh, en };

function detectInitialLocale(): Locale {
  if (typeof window === "undefined") return "zh";
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    if (stored === "zh" || stored === "en") return stored;
  } catch {
    // Private browsing: fall through to the default.
  }
  return "zh";
}

interface I18nContextValue {
  locale: Locale;
  setLocale: (locale: Locale) => void;
  /** Look up `key` in the active dictionary; falls back to zh, then the key itself. */
  t: (key: I18nKey, vars?: Record<string, string | number>) => string;
}

const I18nContext = createContext<I18nContextValue | null>(null);

export function I18nProvider({ children }: { children: ReactNode }) {
  // Start on zh (the historical default and the prerendered shell) and
  // reconcile with localStorage after mount. The async handoff keeps the first
  // client render identical to the server HTML, so hydration stays clean.
  const [locale, setLocaleState] = useState<Locale>("zh");

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setLocaleState((current) => {
        const stored = detectInitialLocale();
        return stored === current ? current : stored;
      });
    }, 0);
    return () => window.clearTimeout(timer);
  }, []);

  useEffect(() => {
    document.documentElement.lang = locale === "en" ? "en" : "zh-CN";
  }, [locale]);

  function setLocale(next: Locale) {
    setLocaleState(next);
    try {
      window.localStorage.setItem(STORAGE_KEY, next);
    } catch {
      // Persistence is best-effort; the in-memory locale still applies.
    }
  }

  function t(key: I18nKey, vars?: Record<string, string | number>): string {
    const template = dictionaries[locale][key] ?? dictionaries.zh[key] ?? key;
    if (!vars) return template;
    return template.replace(/\{(\w+)\}/g, (token, name: string) =>
      vars[name] !== undefined ? String(vars[name]) : token,
    );
  }

  return (
    <I18nContext.Provider value={{ locale, setLocale, t }}>
      {children}
    </I18nContext.Provider>
  );
}

export function useI18n(): I18nContextValue {
  const context = useContext(I18nContext);
  if (!context) throw new Error("useI18n must be used within <I18nProvider>");
  return context;
}
